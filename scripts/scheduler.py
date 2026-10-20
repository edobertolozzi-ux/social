#!/usr/bin/env python3
"""Programmazione dei post sullo scheduler esterno (Upload-Post) e controllo di cosa è uscito.

Programma SOLO i post con stato 'approvato'. Il fornitore si sceglie con la variabile SCHEDULER:
  SCHEDULER=uploadpost  → pubblicazione reale (chiave API come network secret o in UPLOADPOST_API_KEY)
  non impostata         → modalità prova: mostra cosa farebbe, non pubblica niente

Esempi:
  scheduler.py programma clienti/bistrot/piani/2026-11.yaml [--prova] [--solo ID ...] [--subito]
  scheduler.py stato     clienti/bistrot/piani/2026-11.yaml
  scheduler.py riprova   clienti/bistrot/piani/2026-11.yaml 12 [--subito]   (solo post in errore, solo i canali falliti)
  scheduler.py annulla   clienti/bistrot/piani/2026-11.yaml 12
  scheduler.py aggiorna  clienti/bistrot/piani/2026-11.yaml 12 [--caption-dal-piano] [--data 2026-11-20 --ora 19:00]
  scheduler.py profili
  scheduler.py pagine-facebook --profilo bistrot
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import requests
from PIL import Image, ImageOps

from comune import (CACHE, Errore, Media, a_python, adesso, avviso, canali_attivi, carica_config, carica_piano,
                    contiene_segnaposto, data_post, e_video, esegui_main, info, mediapronti, post_numerati,
                    salva_yaml, slug_da_piano, trova_post)

BASE = os.environ.get("UPLOADPOST_BASE", "https://api.upload-post.com/api")
ANTICIPO_MINIMO = dt.timedelta(minutes=10)


# ---------------------------------------------------------------- fornitore

class UploadPost:
    nome = "Upload-Post"

    def __init__(self):
        self.sessione = requests.Session()
        chiave = os.environ.get("UPLOADPOST_API_KEY")
        if chiave:
            self.sessione.headers["Authorization"] = f"Apikey {chiave}"
        # senza chiave nell'ambiente la aggiunge il network secret dell'ambiente cloud

    def _chiama(self, metodo: str, url: str, **kw) -> requests.Response:
        try:
            return self.sessione.request(metodo, url, **kw)
        except requests.RequestException as e:
            raise Errore(f"Upload-Post non raggiungibile ({e.__class__.__name__}): riprova più tardi")

    def _risposta(self, r: requests.Response):
        try:
            dati = r.json()
        except ValueError:
            dati = {"testo": r.text[:500]}
        if r.status_code == 401:
            raise Errore("Upload-Post: chiave API non valida o mancante (controlla il network secret per api.upload-post.com)")
        if r.status_code == 403 and "host_not_allowed" in r.headers.get("x-deny-reason", ""):
            raise Errore("rete: api.upload-post.com non è tra i domini consentiti dell'ambiente cloud")
        if r.status_code >= 400:
            msg = dati.get("message") or dati.get("error") or dati
            raise Errore(f"Upload-Post {r.status_code}: {msg}")
        return dati

    def invia(self, endpoint: str, campi: list[tuple[str, str]], file: list[tuple[str, Path]], chiave_idem: str) -> dict:
        aperti = [(nome, (p.name, open(p, "rb"))) for nome, p in file]
        try:
            r = self._chiama("POST", f"{BASE}/{endpoint}", data=campi, files=aperti,
                             headers={"Idempotency-Key": chiave_idem}, timeout=600)
        finally:
            for _, (_, fh) in aperti:
                fh.close()
        return self._risposta(r)

    def stato(self, job_id: str = "", request_id: str = "") -> dict:
        params = {"job_id": job_id} if job_id else {"request_id": request_id}
        r = self._chiama("GET", f"{BASE}/uploadposts/status", params=params, timeout=60)
        if r.status_code == 404:
            return {"status": "not_found"}
        return self._risposta(r)

    def annulla(self, job_id: str) -> dict:
        return self._risposta(self._chiama("DELETE", f"{BASE}/uploadposts/schedule/{job_id}", timeout=60))

    def aggiorna(self, job_id: str, dati: dict) -> dict:
        return self._risposta(self._chiama("PATCH", f"{BASE}/uploadposts/schedule/{job_id}", json=dati, timeout=60))

    def profili(self) -> dict:
        return self._risposta(self._chiama("GET", f"{BASE}/uploadposts/users", timeout=60))

    def pagine_facebook(self, profilo: str) -> dict:
        return self._risposta(self._chiama("GET", f"{BASE}/uploadposts/facebook/pages", params={"profile": profilo}, timeout=60))


class Prova:
    """Simula lo scheduler: stampa le richieste, non pubblica niente."""
    nome = "PROVA (nessuna pubblicazione)"

    def invia(self, endpoint, campi, file, chiave_idem):
        info(f"    → POST /{endpoint}")
        for k, v in campi:
            v = str(v).replace("\n", " ⏎ ")
            info(f"      {k} = {v[:90]}{'…' if len(v) > 90 else ''}")
        for nome, p in file:
            info(f"      {nome} ← {p.name} ({p.stat().st_size / 1e6:.1f} MB)")
        return {"success": True, "job_id": f"prova-{chiave_idem[:10]}"}

    def stato(self, job_id="", request_id=""):
        return {"status": "pending", "results": []}

    def annulla(self, job_id):
        return {"success": True}

    def aggiorna(self, job_id, dati):
        info(f"    → PATCH /uploadposts/schedule/{job_id} {json.dumps(dati, ensure_ascii=False)[:200]}")
        return {"success": True}

    def profili(self):
        return {"nota": "modalità prova: imposta SCHEDULER=uploadpost per vedere i profili reali"}

    def pagine_facebook(self, profilo):
        return {"nota": "modalità prova"}


def fornitore(prova: bool = False):
    if prova:
        return Prova()
    scelta = os.environ.get("SCHEDULER", "").lower()
    if scelta == "uploadpost":
        return UploadPost()
    if scelta and scelta != "prova":
        raise Errore(f"SCHEDULER='{scelta}' non supportato (valori: uploadpost, prova)")
    avviso("SCHEDULER non impostato: modalità prova, non viene pubblicato niente")
    return Prova()


# ---------------------------------------------------------------- preparazione

def testo_completo(post) -> str:
    caption = (post.get("caption") or "").rstrip()
    hashtag = " ".join(str(h) for h in (post.get("hashtag") or []) if h)
    if hashtag and hashtag not in caption:
        caption = f"{caption}\n\n{hashtag}" if caption else hashtag
    return caption


def prepara_file(media: Media, percorso: str, formato: str) -> Path:
    """Scarica il file finito e lo rende accettabile da Instagram (solo JPEG, rapporto 4:5 – 1.91:1 nel feed)."""
    locale = media.scarica(percorso)
    if e_video(percorso):
        return locale
    with Image.open(locale) as im:
        formato_file = im.format
        orientamento = im.getexif().get(0x0112, 1)
        im = ImageOps.exif_transpose(im)
        rapporto = im.width / im.height
        if formato in ("foto", "carosello") and not (0.79 <= rapporto <= 1.92):
            raise Errore(f"{percorso}: rapporto {rapporto:.2f} non accettato da Instagram nel feed "
                         "(serve tra 4:5 e 1.91:1, ritaglia con grafica.py ritaglia)")
        if formato_file == "JPEG" and im.mode == "RGB" and orientamento in (None, 1):
            return locale
        out = CACHE / "invio" / media.slug / (Path(percorso).stem + ".jpg")
        out.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").save(out, quality=93)
        return out


def richiesta(post, cfg: dict, file_locali: list[Path], subito: bool,
              solo_canali: list[str] | None = None) -> tuple[str, list, list, list[str], list[str]]:
    """Costruisce endpoint, campi e file per un post. Restituisce anche avvisi e canali effettivi."""
    avvisi = []
    formato = post.get("formato")
    canali = [c for c in (post.get("canali") or []) if c in canali_attivi(cfg)]
    if solo_canali:
        canali = [c for c in canali if c in solo_canali]
    if not canali:
        raise Errore("nessun canale attivo per questo post")
    pub = cfg.get("pubblicazione") or {}
    profilo = pub.get("scheduler_profilo") or cfg["slug"]
    campi: list[tuple[str, str]] = [("user", profilo)]
    file: list[tuple[str, Path]] = []
    video = [p for p in file_locali if e_video(p)]

    if formato == "carosello" and video and "facebook" in canali:
        canali = [c for c in canali if c != "facebook"]
        avvisi.append("carosello con video: non viene pubblicato su Facebook, solo su Instagram")
        if not canali:
            raise Errore("carosello con video non pubblicabile su Facebook")

    if formato == "reel" or (formato == "story" and video):
        if len(file_locali) != 1 or not video:
            raise Errore(f"{formato}: serve esattamente un video")
        endpoint = "upload"
        file.append(("video", file_locali[0]))
        tipo = "REELS" if formato == "reel" else "STORIES"
        campi.append(("media_type", tipo))
        if formato == "reel":
            campi.append(("share_to_feed", "true"))
        if "facebook" in canali:
            campi.append(("facebook_media_type", tipo))
    else:
        endpoint = "upload_photos"
        for p in file_locali:
            file.append(("photos[]", p))
        if formato == "story":
            campi.append(("media_type", "STORIES"))
            if "facebook" in canali:
                campi.append(("facebook_media_type", "STORIES"))
        else:
            campi.append(("media_type", "IMAGE"))

    for c in canali:
        campi.append(("platform[]", c))
    if "facebook" in canali:
        if not pub.get("facebook_page_id"):
            raise Errore("manca pubblicazione.facebook_page_id in config.yaml (scheduler.py pagine-facebook --profilo ...)")
        campi.append(("facebook_page_id", str(pub["facebook_page_id"])))

    if formato != "story":
        campi.append(("title", testo_completo(post)))
        if post.get("primo_commento"):
            campi.append(("first_comment", str(post["primo_commento"])))
        if post.get("alt_text") and endpoint == "upload_photos":
            campi.append(("instagram_alt_text", str(post["alt_text"])))
    if (post.get("media") or {}).get("lavorazione") in ("ai_immagine", "ai_video"):
        campi.append(("is_ai_generated", "true"))

    if not subito:
        quando = data_post(post)
        campi.append(("scheduled_date", quando.strftime("%Y-%m-%dT%H:%M:%S")))
        campi.append(("timezone", pub.get("fuso_orario", "Europe/Rome")))
    else:
        campi.append(("async_upload", "true"))
    campi.append(("external_id", f"{cfg['slug']}/{post.get('id')}"))
    return endpoint, campi, file, avvisi, canali


def chiave_idempotenza(slug: str, post, campi) -> str:
    base = json.dumps([slug, post.get("id"), [c for c in campi if c[0] in ("scheduled_date", "title", "platform[]")],
                       [str(x) for x in mediapronti(post)]], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(base.encode()).hexdigest()[:40]


def _scheduler_di(post) -> dict:
    if not isinstance(post.get("scheduler"), dict):
        post["scheduler"] = {}
    return post["scheduler"]


def _invia_post(post, slug, cfg, media, sched, subito, solo_canali=None) -> tuple[dict, list[str]]:
    """Prepara i file e invia un post allo scheduler. Restituisce risposta e canali inviati."""
    if contiene_segnaposto(post):
        raise Errore("contiene ancora [DA VERIFICARE]: completa il testo prima di programmare")
    locali = [prepara_file(media, p, post.get("formato")) for p in mediapronti(post)]
    endpoint, campi, file, avvisi, canali = richiesta(post, cfg, locali, subito, solo_canali)
    for w in avvisi:
        avviso(f"post {post.get('id')}: {w}")
    risposta = sched.invia(endpoint, campi, file, chiave_idempotenza(slug, post, campi))
    return risposta, canali


def _registra_invio(post, risposta: dict, canali: list[str], subito: bool) -> None:
    sch = _scheduler_di(post)
    piattaforme = dict(sch.get("piattaforme") or {})
    for c in canali:
        piattaforme[c] = "in coda"
    sch.update({
        "job_id": risposta.get("job_id") or "",
        "request_id": risposta.get("request_id") or "",
        "programmato_il": adesso().isoformat(timespec="seconds"),
        "canali_job": canali,
        "piattaforme": piattaforme,
        "errore": "",
    })
    sch.setdefault("url", "")
    risultati = risposta.get("results")
    if subito and isinstance(risultati, dict) and risultati:
        for c, v in risultati.items():
            if isinstance(v, dict) and not v.get("skipped"):
                piattaforme[c] = "pubblicato" if v.get("success") else f"errore: {v.get('error') or v.get('message') or ''}"
                sch["url"] = sch.get("url") or v.get("url") or ""
        post["stato"] = _stato_complessivo(post, piattaforme, "pubblicato")
    else:
        post["stato"] = "programmato"


def _stato_complessivo(post, piattaforme: dict, stato_job: str) -> str:
    """pubblicato se è uscito su tutti i canali inviati, errore se almeno uno è fallito, altrimenti programmato."""
    attesi = [c for c in (post.get("canali") or []) if c in piattaforme] or list(piattaforme)
    if attesi and all(piattaforme.get(c) == "pubblicato" for c in attesi):
        return "pubblicato"
    if any(str(v).startswith("errore") for v in piattaforme.values()):
        return "errore"
    return "programmato"


# ---------------------------------------------------------------- comandi

def cmd_programma(a):
    piano = carica_piano(a.piano)
    slug = slug_da_piano(a.piano, piano)
    cfg = carica_config(slug)
    media = Media(slug)
    sched = fornitore(a.prova)
    a.prova = a.prova or isinstance(sched, Prova)
    info(f"Scheduler: {sched.nome} · cliente {cfg.get('nome')} · {piano.get('mese')}")
    programmati, saltati = 0, []
    limite = adesso() + ANTICIPO_MINIMO
    for n, post in post_numerati(piano):
        scelto = not a.solo or post.get("id") in a.solo or str(n) in a.solo
        if not scelto:
            continue
        stato = post.get("stato")
        if stato != "approvato":
            if a.solo:
                suggerimento = " (usa: scheduler.py riprova)" if stato == "errore" else ""
                saltati.append(f"{n}: stato '{stato}', si programmano solo i post approvati{suggerimento}")
            continue
        sch = post.get("scheduler") if isinstance(post.get("scheduler"), dict) else {}
        if sch.get("job_id") and not a.prova:
            saltati.append(f"{n}: risulta già inviato allo scheduler (job {sch['job_id']}), non lo rimando")
            continue
        if not a.subito and data_post(post) < limite:
            saltati.append(f"{n} ({post.get('id')}): data già passata o troppo vicina, scegli un nuovo orario")
            continue
        if not mediapronti(post):
            saltati.append(f"{n}: nessun file in media.pronto")
            continue
        info(f"  {n:>2}. {post.get('data')} {post.get('ora')} {post.get('formato')} → {', '.join(post.get('canali') or [])}")
        try:
            risposta, canali = _invia_post(post, slug, cfg, media, sched, a.subito)
        except Errore as e:
            saltati.append(f"{n}: {e}")
            if not a.prova:
                _scheduler_di(post)["errore"] = str(e)
                salva_yaml(a.piano, piano)
            continue
        programmati += 1
        if a.prova:
            continue
        _registra_invio(post, risposta, canali, a.subito)
        salva_yaml(a.piano, piano)   # salva dopo ogni post: se qualcosa si interrompe non si perde niente
    if not a.prova and programmati:
        if all(p.get("stato") in ("programmato", "pubblicato", "scartato") for p in piano["post"]):
            piano["stato_piano"] = "programmato"
        salva_yaml(a.piano, piano)
        from piano import cmd_segna_usate
        cmd_segna_usate(argparse.Namespace(piano=a.piano))
    verbo = "da programmare (prova)" if a.prova else "programmati"
    info(f"{programmati} post {verbo}.")
    for s_ in saltati:
        info(f"  saltato: {s_}")
    return 1 if saltati and not programmati else 0


def _interpreta_stato(dati: dict) -> tuple[str, str, str, dict]:
    """Da risposta Upload-Post a (stato del job, url, errore, esito per piattaforma)."""
    stato = str(dati.get("status", "")).lower()
    risultati = dati.get("results") or []
    if isinstance(risultati, dict):
        risultati = [{"platform": k, **v} for k, v in risultati.items() if isinstance(v, dict)]
    url = next((r.get("post_url") or r.get("url") or "" for r in risultati if r.get("post_url") or r.get("url")), "")
    per_piattaforma = {}
    for r in risultati:
        if r.get("skipped") or not r.get("platform"):
            continue
        if r.get("success") is True:
            per_piattaforma[r["platform"]] = "pubblicato"
        elif r.get("success") is False:
            per_piattaforma[r["platform"]] = f"errore: {r.get('message') or r.get('error') or 'errore'}"
    falliti = [f"{k}: {v[8:]}" for k, v in per_piattaforma.items() if v.startswith("errore")]
    if stato == "completed":
        return ("errore" if falliti else "pubblicato"), url, "; ".join(falliti), per_piattaforma
    if stato == "failed":
        return "errore", url, dati.get("message") or "; ".join(falliti) or "pubblicazione fallita", per_piattaforma
    if stato == "not_found":
        return "errore", "", "job non trovato sullo scheduler (cancellato?)", per_piattaforma
    return "programmato", url, "", per_piattaforma


def cmd_stato(a):
    piano = carica_piano(a.piano)
    slug_da_piano(a.piano, piano)
    sched = fornitore(a.prova)
    if isinstance(sched, Prova):
        info("Modalità prova: stato non controllato.")
        return 0
    ora = adesso()
    cambiati, errori = 0, []
    for n, post in post_numerati(piano):
        if post.get("stato") not in ("programmato", "errore"):
            continue
        sch = _scheduler_di(post)
        if not (sch.get("job_id") or sch.get("request_id")):
            continue
        if post.get("stato") == "programmato" and data_post(post) > ora:
            continue   # non ancora uscito
        try:
            dati = sched.stato(sch.get("job_id", ""), sch.get("request_id", ""))
        except Errore as e:
            avviso(f"post {n}: {e}")
            continue
        stato_job, url, errore, per_piattaforma = _interpreta_stato(dati)
        piattaforme = dict(sch.get("piattaforme") or {})
        if not per_piattaforma and stato_job in ("pubblicato", "errore"):
            # nessun dettaglio per piattaforma: vale per tutti i canali di questo invio
            for c in (sch.get("canali_job") or post.get("canali") or []):
                piattaforme[c] = "pubblicato" if stato_job == "pubblicato" else f"errore: {errore}"
        piattaforme.update(per_piattaforma)
        nuovo = _stato_complessivo(post, piattaforme, stato_job) if stato_job != "programmato" else "programmato"
        if nuovo == "errore" and not errore:
            errore = "; ".join(f"{k}: {v[8:]}" for k, v in piattaforme.items() if str(v).startswith("errore"))
        if nuovo != post.get("stato") or url and url != sch.get("url") or piattaforme != sch.get("piattaforme"):
            post["stato"] = nuovo
            sch["url"] = sch.get("url") or url
            sch["errore"] = errore if nuovo == "errore" else ""
            sch["piattaforme"] = piattaforme
            cambiati += 1
        if nuovo == "errore":
            errori.append(f"{n}. {post.get('data')} {post.get('ora')} {post.get('formato')}: {errore}")
    if cambiati:
        salva_yaml(a.piano, piano)
    pubblicati = sum(1 for p in piano["post"] if p.get("stato") == "pubblicato")
    in_coda = sum(1 for p in piano["post"] if p.get("stato") == "programmato")
    info(f"{piano.get('cliente')} {piano.get('mese')}: {pubblicati} pubblicati, {in_coda} in coda, {len(errori)} errori.")
    for e in errori:
        info(f"  ERRORE {e}")
    return 0


def cmd_riprova(a):
    """Rimanda un post in errore SOLO sulle piattaforme dove non è uscito (niente doppioni)."""
    piano = carica_piano(a.piano)
    slug = slug_da_piano(a.piano, piano)
    cfg = carica_config(slug)
    n, post = trova_post(piano, a.post)
    if post.get("stato") != "errore":
        raise Errore(f"il post {n} è '{post.get('stato')}': si riprovano solo i post in errore")
    sch = _scheduler_di(post)
    piattaforme = dict(sch.get("piattaforme") or {})
    canali = [c for c in (post.get("canali") or []) if piattaforme.get(c) != "pubblicato"]
    if not canali:
        raise Errore(f"il post {n} risulta già pubblicato su tutti i canali")
    if not a.subito and data_post(post) < adesso() + ANTICIPO_MINIMO:
        raise Errore("la data del post è passata: usa --subito per pubblicare adesso, oppure sposta il post")
    sched = fornitore(a.prova)
    if isinstance(sched, Prova):
        info(f"Modalità prova: il post {n} verrebbe rimandato su {', '.join(canali)}.")
        return 0
    risposta, inviati = _invia_post(post, slug, cfg, Media(slug), sched, a.subito, solo_canali=canali)
    tentativi = list(sch.get("tentativi") or [])
    tentativi.append({"job_id": sch.get("job_id", ""), "request_id": sch.get("request_id", ""), "errore": sch.get("errore", "")})
    sch["tentativi"] = tentativi
    _registra_invio(post, risposta, inviati, a.subito)
    salva_yaml(a.piano, piano)
    info(f"Post {n} rimandato su {', '.join(inviati)} ({post['stato']}).")
    return 0


def cmd_annulla(a):
    piano = carica_piano(a.piano)
    slug_da_piano(a.piano, piano)
    n, post = trova_post(piano, a.post)
    sch = _scheduler_di(post)
    if post.get("stato") != "programmato" or not sch.get("job_id"):
        raise Errore(f"il post {n} è '{post.get('stato')}': si annullano solo i post programmati e non ancora usciti")
    sched = fornitore(a.prova)
    if isinstance(sched, Prova):
        info(f"Modalità prova: il post {n} verrebbe tolto dalla programmazione.")
        return 0
    sched.annulla(sch["job_id"])
    post["scheduler"] = {"job_id": "", "programmato_il": "", "url": "", "errore": ""}
    post["stato"] = "approvato"
    salva_yaml(a.piano, piano)
    info(f"Post {n} tolto dalla programmazione (resta approvato).")
    return 0


def cmd_aggiorna(a):
    piano = carica_piano(a.piano)
    slug = slug_da_piano(a.piano, piano)
    cfg = carica_config(slug)
    n, post = trova_post(piano, a.post)
    sch = _scheduler_di(post)
    if post.get("stato") != "programmato" or not sch.get("job_id"):
        raise Errore(f"il post {n} non è in coda sullo scheduler: usa programma")
    dati = {}
    if a.data or a.ora:
        prova_data = {"id": post.get("id"), "data": a.data or post.get("data"), "ora": a.ora or post.get("ora")}
        quando = data_post(prova_data)
        if piano.get("mese") and not str(prova_data["data"]).startswith(str(piano["mese"])):
            raise Errore(f"la data {prova_data['data']} è fuori dal mese del piano ({piano['mese']})")
        if quando < adesso() + ANTICIPO_MINIMO:
            raise Errore("la nuova data è già passata o troppo vicina")
        post["data"], post["ora"] = prova_data["data"], prova_data["ora"]
        dati["scheduled_date"] = quando.strftime("%Y-%m-%dT%H:%M:%S")
        dati["timezone"] = cfg["pubblicazione"].get("fuso_orario", "Europe/Rome")
    if a.caption_dal_piano:
        if contiene_segnaposto(post):
            raise Errore("la caption contiene ancora [DA VERIFICARE]")
        dati["title"] = testo_completo(post)
    if not dati:
        raise Errore("niente da aggiornare: usa --data/--ora e/o --caption-dal-piano")
    sched = fornitore(a.prova)
    sched.aggiorna(sch["job_id"], dati)
    if isinstance(sched, Prova):
        info("Modalità prova: niente salvato.")
        return 0
    salva_yaml(a.piano, piano)
    info(f"Post {n} aggiornato sullo scheduler.")
    return 0


def cmd_profili(a):
    dati = fornitore(a.prova).profili()
    profili = dati.get("profiles") or dati.get("users") or dati.get("data")
    if isinstance(profili, list):
        for p in profili:
            nome = p.get("username") or p.get("profile_username") or p.get("name")
            social = p.get("social_accounts") or p.get("platforms") or {}
            if isinstance(social, dict):
                collegati = [k for k, v in social.items() if v]
            else:
                collegati = [str(s) for s in social]
            info(f"{nome}: {', '.join(collegati) or 'nessun account collegato'}")
    else:
        print(json.dumps(a_python(dati), ensure_ascii=False, indent=2)[:3000])
    return 0


def cmd_pagine_facebook(a):
    dati = fornitore(a.prova).pagine_facebook(a.profilo)
    pagine = dati.get("pages")
    if isinstance(pagine, list):
        for p in pagine:
            info(f"{p.get('page_id') or p.get('id')}  {p.get('page_name') or p.get('name')}")
    else:
        print(json.dumps(a_python(dati), ensure_ascii=False, indent=2)[:3000])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("programma"); s.add_argument("piano")
    s.add_argument("--solo", nargs="+", help="solo questi post (id o numero)")
    s.add_argument("--subito", action="store_true", help="pubblica adesso invece che alla data del post")
    s.add_argument("--prova", action="store_true"); s.set_defaults(f=cmd_programma)

    s = sub.add_parser("stato"); s.add_argument("piano"); s.add_argument("--prova", action="store_true")
    s.set_defaults(f=cmd_stato)

    s = sub.add_parser("riprova", help="rimanda un post in errore solo dove non è uscito")
    s.add_argument("piano"); s.add_argument("post"); s.add_argument("--subito", action="store_true")
    s.add_argument("--prova", action="store_true"); s.set_defaults(f=cmd_riprova)

    s = sub.add_parser("annulla"); s.add_argument("piano"); s.add_argument("post")
    s.add_argument("--prova", action="store_true"); s.set_defaults(f=cmd_annulla)

    s = sub.add_parser("aggiorna"); s.add_argument("piano"); s.add_argument("post")
    s.add_argument("--data"); s.add_argument("--ora"); s.add_argument("--caption-dal-piano", action="store_true")
    s.add_argument("--prova", action="store_true"); s.set_defaults(f=cmd_aggiorna)

    s = sub.add_parser("profili"); s.add_argument("--prova", action="store_true"); s.set_defaults(f=cmd_profili)
    s = sub.add_parser("pagine-facebook"); s.add_argument("--profilo", required=True)
    s.add_argument("--prova", action="store_true"); s.set_defaults(f=cmd_pagine_facebook)

    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    esegui_main(main)
