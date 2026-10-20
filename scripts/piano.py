#!/usr/bin/env python3
"""Modifiche rapide e sicure ai piani editoriali (pensato per i comandi vocali di Edoardo).

I post si indicano col numero del calendario (1, 2, 3... in ordine di data) oppure con l'id.

Esempi:
  piano.py elenco clienti/bistrot/piani/2026-11.yaml [--breve]
  piano.py approva clienti/bistrot/piani/2026-11.yaml --tutti --tranne 3 7
  piano.py approva clienti/bistrot/piani/2026-11.yaml 1 2 5
  piano.py scarta  clienti/bistrot/piani/2026-11.yaml 9
  piano.py sposta  clienti/bistrot/piani/2026-11.yaml 12 --data 2026-11-20 --ora 19:00
  piano.py imposta clienti/bistrot/piani/2026-11.yaml --post 5 stato=bozza note_edoardo="più ironica"
  piano.py imposta clienti/bistrot/piani/2026-11.yaml --piano stato_piano=pronto
  piano.py aggiungi clienti/bistrot/piani/2026-11.yaml --da-json '{"data":"2026-11-14", ...}'
  piano.py stato-mese --mese 2026-11
  piano.py segna-usate clienti/bistrot/piani/2026-11.yaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import string
from collections import Counter
from pathlib import Path

from comune import (CLIENTI, GIORNI_BREVI, STATI_POST, Errore, carica_piano, carica_yaml, cartella_cliente, contiene_segnaposto,
                    elenco_slug, esegui_main, info, mese_prossimo, oggi, percorso_piano, post_numerati,
                    salva_yaml, slug_da_piano, trova_post, valida_mese, avviso)
from ruamel.yaml import YAML


def _etichetta(p) -> str:
    try:
        d = dt.date.fromisoformat(str(p.get("data")))
        giorno = f"{GIORNI_BREVI[d.weekday()]} {d.day:02d}"
    except ValueError:
        giorno = str(p.get("data"))
    return f"{giorno} {p.get('ora') or '--:--'}"


def _riassunto(p, larghezza=60) -> str:
    testo = (p.get("caption") or "").strip().split("\n")[0] or (p.get("idea") or "")
    testo = re.sub(r"\s+", " ", testo)
    return testo[: larghezza - 1] + "…" if len(testo) > larghezza else testo


def cmd_elenco(a):
    piano = carica_piano(a.piano)
    numerati = post_numerati(piano)
    conta = Counter(p.get("stato", "bozza") for _, p in numerati)
    intestazione = f"{piano.get('cliente', '')} · {piano.get('mese', '')} · piano {piano.get('stato_piano', 'bozza')}"
    info(intestazione)
    info("  " + ", ".join(f"{s}: {conta[s]}" for s in STATI_POST if conta[s]))
    if a.breve:
        da_vedere = [(n, p) for n, p in numerati if p.get("stato") in ("da_correggere", "bozza", "da_rivedere", "errore")]
        for n, p in da_vedere:
            nota = (p.get("revisione") or {}).get("note") or (p.get("scheduler") or {}).get("errore") or ""
            info(f"  {n:>2}. {_etichetta(p)} {p.get('formato', '')} · {p.get('stato')} {('- ' + nota) if nota else ''}")
        return 0
    for n, p in numerati:
        canali = "+".join({"instagram": "IG", "facebook": "FB"}.get(c, c[:2].upper()) for c in (p.get("canali") or []))
        info(f"{n:>3}. {_etichetta(p)}  {str(p.get('formato', '')):<9} {canali:<5} {str(p.get('stato', 'bozza')):<13} {_riassunto(p)}  [{p.get('id')}]")
    return 0


def _numeri(piano, rif: list[str]) -> list[tuple[int, dict]]:
    return [trova_post(piano, r) for r in rif]


def cmd_approva(a):
    piano = carica_piano(a.piano)
    if a.tutti:
        esclusi = {trova_post(piano, r)[0] for r in (a.tranne or [])}
        scelti = [(n, p) for n, p in post_numerati(piano) if n not in esclusi and p.get("stato") == "pronto"]
        saltati = [(n, p) for n, p in post_numerati(piano)
                   if n not in esclusi and p.get("stato") in ("bozza", "da_rivedere", "da_correggere")]
    else:
        if not a.post:
            raise Errore("indica i numeri dei post oppure --tutti")
        scelti, saltati = [], []
        for n, p in _numeri(piano, a.post):
            if p.get("stato") in ("bozza", "da_rivedere"):
                saltati.append((n, p))
            else:
                scelti.append((n, p))
    approvati, bloccati = [], []
    for n, p in scelti:
        if p.get("stato") in ("programmato", "pubblicato", "approvato"):
            continue
        if p.get("stato") == "errore":
            bloccati.append(f"{n} (in errore: usa scheduler.py riprova)")
            continue
        if contiene_segnaposto(p):
            bloccati.append(f"{n} (contiene [DA VERIFICARE])")
            continue
        if p.get("stato") == "da_correggere":
            avviso(f"post {n}: approvato anche se il revisore chiedeva correzioni ({(p.get('revisione') or {}).get('note', '')})")
        p["stato"] = "approvato"
        approvati.append(n)
    salva_yaml(a.piano, piano)
    info(f"Approvati: {', '.join(map(str, approvati)) or 'nessuno'}")
    if bloccati:
        info("Non approvati: " + ", ".join(bloccati))
    if saltati:
        info("Non approvabili (contenuto non pronto): " + ", ".join(f"{n} ({p.get('stato')})" for n, p in saltati))
    if a.tranne:
        info(f"Lasciati fuori su richiesta: {', '.join(a.tranne)}")
    return 0


def cmd_scarta(a):
    piano = carica_piano(a.piano)
    fatti = []
    for n, p in _numeri(piano, a.post):
        if p.get("stato") == "programmato":
            avviso(f"post {n} è già programmato: prima annullalo con scheduler.py annulla")
            continue
        p["stato"] = "scartato"
        fatti.append(str(n))
    salva_yaml(a.piano, piano)
    info(f"Scartati: {', '.join(fatti) or 'nessuno'}")
    return 0


def cmd_sposta(a):
    piano = carica_piano(a.piano)
    n, p = trova_post(piano, a.post)
    if a.data:
        try:
            dt.date.fromisoformat(a.data)
        except ValueError:
            raise Errore(f"data non valida '{a.data}': usa AAAA-MM-GG")
        if piano.get("mese") and not a.data.startswith(str(piano["mese"])):
            raise Errore(f"la data {a.data} è fuori dal mese del piano ({piano['mese']})")
        p["data"] = a.data
    if a.ora:
        if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", a.ora):
            raise Errore("ora non valida, usa HH:MM")
        p["ora"] = a.ora
    salva_yaml(a.piano, piano)
    info(f"Post {p.get('id')} spostato a {_etichetta(p)}.")
    if p.get("stato") == "programmato":
        info("È già programmato: aggiorna anche lo scheduler con  scheduler.py aggiorna <piano> "
             f"{p.get('id')} --data {p['data']} --ora {p['ora']}")
    return 0


CAMPI_TESTO = {"caption", "idea", "note", "note_edoardo", "note_per_edoardo", "primo_commento", "alt_text",
               "obiettivo", "obiettivo_mese", "pilastro", "prompt_ai", "titolo", "sottotitolo", "ora", "data", "id",
               "esito", "stato", "stato_piano", "template", "lavorazione"}


def _valore(chiave: str, testo: str):
    """Interpreta il valore di 'campo=valore' in modo prudente.

    - campi di testo (caption, note, ...): sempre testo, anche se contengono ':' o '['
    - hashtag: lista di parole che iniziano con #, separate da spazi o virgole
    - altri campi: liste/oggetti in sintassi YAML ([a, b] o {k: v}), numeri e booleani
    """
    ultimo = chiave.split(".")[-1]
    t = testo.strip()
    if ultimo in CAMPI_TESTO:
        return testo
    if ultimo == "hashtag":
        parole = [x for x in re.split(r"[\s,\[\]]+", t) if x]
        sbagliati = [x for x in parole if not x.startswith("#")]
        if sbagliati:
            raise Errore(f"hashtag non validi: {' '.join(sbagliati)} (ognuno deve iniziare con #)")
        return parole
    if t.startswith(("[", "{")):
        try:
            return YAML(typ="safe").load(t)
        except Exception:
            raise Errore(f"'{chiave}': valore non leggibile come lista/oggetto: {testo}")
    if re.fullmatch(r"-?\d+(\.\d+)?|true|false|null", t):
        return YAML(typ="safe").load(t)
    return testo


def _assegna(obj: dict, chiave: str, valore):
    parti = chiave.split(".")
    for parte in parti[:-1]:
        if obj.get(parte) is None:
            obj[parte] = {}
        obj = obj[parte]
    obj[parti[-1]] = valore


def cmd_imposta(a):
    piano = carica_piano(a.piano)
    bersaglio = piano
    if a.post:
        _, bersaglio = trova_post(piano, a.post)
    for assegnazione in a.assegnazioni:
        if "=" not in assegnazione:
            raise Errore(f"'{assegnazione}' non è nel formato campo=valore")
        chiave, valore = assegnazione.split("=", 1)
        valore = _valore(chiave.strip(), valore)
        if chiave == "stato" and valore not in STATI_POST:
            raise Errore(f"stato '{valore}' non valido")
        _assegna(bersaglio, chiave.strip(), valore)
    if not a.post:
        piano["aggiornato"] = oggi().isoformat()
    salva_yaml(a.piano, piano)
    info("Fatto.")
    return 0


def _prossimo_id(piano, data: str) -> str:
    usati = {str(p.get("id")) for p in piano["post"]}
    for lettera in string.ascii_lowercase:
        candidato = f"{data}-{lettera}"
        if candidato not in usati:
            return candidato
    raise Errore("troppi post nello stesso giorno")


def _piano_vuoto(percorso: Path) -> dict:
    slug = percorso.resolve().relative_to(CLIENTI.resolve()).parts[0]
    return {"cliente": slug, "mese": percorso.stem, "stato_piano": "bozza", "aggiornato": oggi().isoformat(),
            "strategia": {"obiettivo_mese": "", "pilastri": [], "ricorrenze": [], "note_per_edoardo": ""},
            "post": []}


def cmd_aggiungi(a):
    percorso = Path(a.piano)
    piano = carica_piano(percorso) if percorso.exists() else _piano_vuoto(percorso)
    try:
        post = json.loads(a.da_json)
    except json.JSONDecodeError as e:
        raise Errore(f"JSON non valido: {e}")
    if "data" not in post:
        raise Errore("il post deve avere almeno 'data'")
    post.setdefault("id", _prossimo_id(piano, post["data"]))
    if any(str(p.get("id")) == post["id"] for p in piano["post"]):
        raise Errore(f"id {post['id']} già presente")
    post.setdefault("ora", "12:00")
    post.setdefault("canali", ["instagram", "facebook"])
    post.setdefault("formato", "foto")
    post.setdefault("stato", "bozza")
    post.setdefault("media", {"lavorazione": "nessuna", "sorgente": [], "pronto": []})
    post.setdefault("caption", "")
    post.setdefault("hashtag", [])
    piano["post"].append(post)
    salva_yaml(percorso, piano)
    numero = trova_post(piano, post["id"])[0]
    info(f"Aggiunto post {numero} con id {post['id']}.")
    return 0


def cmd_stato_mese(a):
    mese = valida_mese(a.mese or mese_prossimo())
    info(f"Piani di {mese}:")
    for slug in elenco_slug(solo_attivi=True):
        p = percorso_piano(slug, mese)
        if not p.exists():
            info(f"  {slug:<24} nessun piano")
            continue
        piano = carica_piano(p)
        conta = Counter(x.get("stato", "bozza") for x in piano["post"])
        dettaglio = ", ".join(f"{k} {v}" for k, v in conta.items())
        info(f"  {slug:<24} {piano.get('stato_piano', 'bozza'):<11} {len(piano['post'])} post ({dettaglio})")
    return 0


def cmd_segna_usate(a):
    piano = carica_piano(a.piano)
    slug = slug_da_piano(a.piano, piano)
    p_media = cartella_cliente(slug) / "media.yaml"
    if not p_media.exists():
        return 0
    catalogo = carica_yaml(p_media)
    per_percorso = {str(v.get("percorso")): v for v in (catalogo.get("file") or [])}
    cambiati = 0
    for p in piano["post"]:
        if p.get("stato") not in ("approvato", "programmato", "pubblicato"):
            continue
        for s in ((p.get("media") or {}).get("sorgente") or []):
            voce = per_percorso.get(str(s))
            if voce is None:
                continue
            usata = voce.get("usata_in") or []
            if p["id"] not in usata:
                usata.append(p["id"])
                voce["usata_in"] = usata
                cambiati += 1
    if cambiati:
        salva_yaml(p_media, catalogo)
    info(f"Catalogo aggiornato ({cambiati} utilizzi registrati).")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("elenco", help="elenco numerato dei post")
    s.add_argument("piano"); s.add_argument("--breve", action="store_true"); s.set_defaults(f=cmd_elenco)

    s = sub.add_parser("approva", help="approva post")
    s.add_argument("piano"); s.add_argument("post", nargs="*")
    s.add_argument("--tutti", action="store_true"); s.add_argument("--tranne", nargs="*")
    s.set_defaults(f=cmd_approva)

    s = sub.add_parser("scarta", help="scarta post")
    s.add_argument("piano"); s.add_argument("post", nargs="+"); s.set_defaults(f=cmd_scarta)

    s = sub.add_parser("sposta", help="cambia data e/o ora di un post")
    s.add_argument("piano"); s.add_argument("post"); s.add_argument("--data"); s.add_argument("--ora")
    s.set_defaults(f=cmd_sposta)

    s = sub.add_parser("imposta", help="imposta campi del piano o di un post (campo.sotto=valore)")
    s.add_argument("piano"); s.add_argument("--post"); s.add_argument("--piano", dest="livello_piano", action="store_true")
    s.add_argument("assegnazioni", nargs="+"); s.set_defaults(f=cmd_imposta)

    s = sub.add_parser("aggiungi", help="aggiunge un post (crea il piano se non esiste)")
    s.add_argument("piano"); s.add_argument("--da-json", required=True); s.set_defaults(f=cmd_aggiungi)

    s = sub.add_parser("stato-mese", help="a che punto sono i piani di tutti i clienti")
    s.add_argument("--mese"); s.set_defaults(f=cmd_stato_mese)

    s = sub.add_parser("segna-usate", help="registra in media.yaml le foto usate dai post approvati")
    s.add_argument("piano"); s.set_defaults(f=cmd_segna_usate)

    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    esegui_main(main)
