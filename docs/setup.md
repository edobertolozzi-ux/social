# Configurazione iniziale (una volta sola, circa un'ora, dal computer)

Alla fine di questa guida potrai fare tutto dall'iPhone: app Claude → scheda **Code** → sessione su `volta-social`.

## Cosa ti serve

| Servizio | A cosa serve | Costo |
|---|---|---|
| Claude (Max) | il cervello: agenti, chat, routine | già incluso nell'abbonamento |
| GitHub | la "cartella unica" con tutti i clienti | gratis (repository privato) |
| Upload-Post | pubblica su Instagram e Facebook all'orario giusto | Basic 19 €/mese (5 profili = 5 clienti); Professional 50 $/mese, 33 $/mese con pagamento annuale (25 profili) |
| Google Drive | foto e video dei clienti | quello che hai già |
| OpenRouter | immagini e video AI | a consumo, ricarica prepagata (es. 10 $) |
| Cloudflare Pages | pagina calendario privata | gratis |

---

## 1. Repository su GitHub

1. Crea un account su github.com (se non ce l'hai).
2. **New repository** → nome `volta-social` → **Private** → senza README → **Create**.
3. Caricare i file: **dimmelo in chat e lo carico io**. In alternativa, da Claude Code sul computer: apri la cartella `volta-social` scompattata e scrivi "carica questo progetto sul mio repository GitHub volta-social, branch main".

## 2. Collega GitHub a Claude Code

1. Vai su **claude.ai/code** e completa l'onboarding.
2. Quando lo chiede, installa la **Claude GitHub App** e dalle accesso al repository `volta-social`.

## 3. Accesso a Google Drive (token per rclone)

Gli script leggono e scrivono su Drive con `rclone`. Serve un "token" che si ottiene una volta dal computer:

1. Installa rclone: su Mac `brew install rclone` (oppure scarica da rclone.org/downloads).
2. Nel Terminale: `rclone authorize "drive"` → si apre il browser → accedi con il tuo account Google → **Consenti**.
3. Il Terminale stampa un testo tra `--->` e `<---End paste`: copia **solo** la parte `{"access_token":...}` (tutta, fino alla graffa finale).

Su Drive crea la cartella **VOLTA** nel tuo "Il mio Drive": dentro ci saranno le cartelle dei clienti (le crea lo strumento). Ai clienti condividi solo la loro sottocartella `materiali` per caricare foto e video.

## 4. Ambiente cloud (la parte più importante)

Su **claude.ai/code** → selettore dell'ambiente sotto la casella di testo → **Add environment**, nome `VOLTA`:

**Network access** → **Custom** → spunta *Also include default list of common package managers* → in **Allowed domains** aggiungi:
```
api.upload-post.com
openrouter.ai
cdn.playwright.dev
playwright.download.prss.microsoft.com
playwright.azureedge.net
```
(se un cliente usa Dropbox aggiungi anche `api.dropboxapi.com` e `content.dropboxapi.com`)

**Environment variables** (una per riga):
```
SCHEDULER=uploadpost
EMAIL_EDOARDO=la-tua-email@gmail.com
CALENDARIO_URL=https://volta-social.pages.dev
RCLONE_CONFIG_DRIVE_TYPE=drive
RCLONE_CONFIG_DRIVE_SCOPE=drive
RCLONE_CONFIG_DRIVE_TOKEN='{"access_token":"...incolla qui il token del passo 3..."}'
```
Il token va tra apici singoli. Le variabili sono visibili a chi usa l'ambiente: solo tu.

**Setup script**: incolla tutto il contenuto di `setup/ambiente-cloud.sh`.

**Network secrets** (le chiavi restano fuori dalla sessione, Claude non le vede mai):
- **Upload-Post**: host `api.upload-post.com`, header `Authorization`, prefisso `Apikey`, valore = la tua chiave API (passo 5)
- **OpenRouter**: host `openrouter.ai`, header `Authorization`, prefisso `Bearer`, valore = la chiave (passo 6)

Salva. Il primo avvio dell'ambiente richiede qualche minuto (installa ffmpeg, rclone, il browser per le grafiche); poi resta in cache.

## 5. Upload-Post (lo scheduler)

1. Registrati su upload-post.com, scegli il piano (Basic per partire), crea una **API key**.
2. Per ogni cliente: **crea un profilo** con lo stesso nome dello slug del cliente (es. `la-bolla`) e collega **Instagram** (account Business o Creator, collegato a una Pagina Facebook) e la **Pagina Facebook**. Il tuo profilo Facebook deve essere amministratore della Pagina.
3. In una sessione di Claude scrivi "controlla i profili dello scheduler": Claude esegue `scheduler.py profili` (cosa è collegato) e `scheduler.py pagine-facebook --profilo <slug>` (per il `facebook_page_id`), e compila la config del cliente.

## 6. OpenRouter (immagini e video AI)

1. Registrati su openrouter.ai, ricarica il credito (es. 10 $).
2. Crea una API key e impostale un **limite di credito** mensile (es. 30 $): è la cintura di sicurezza oltre ai tetti per cliente.

## 7. Pagina calendario (Cloudflare Pages, gratis)

1. Registrati su cloudflare.com → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** → scegli `volta-social`.
2. Build command: vuoto. **Build output directory: `site`**. Branch: `main`. Deploy.
3. Rendila privata: **Zero Trust** → **Access** → **Applications** → **Add an application** → *Self-hosted* → dominio `volta-social.pages.dev` → policy *Allow* con *Emails* = la tua email. Accederai con un codice che ti arriva per email (una volta ogni tanto).
4. Copia l'indirizzo nella variabile `CALENDARIO_URL` dell'ambiente (passo 4).

Da qui in poi la pagina si aggiorna da sola a ogni salvataggio.

## 8. Connettori di Claude

Su claude.ai → impostazioni → **Connettori**: tieni collegati **Gmail** (avvisi e bozze dei report) e **Google Drive**.

## 9. Prova dal telefono

App Claude → **Code** → nuova sessione → repository `volta-social`, ambiente `VOLTA` → scrivi:

> verifica il setup

Claude esegue `scripts/verifica_setup.py` e ti dice cosa manca. Quando è tutto ✓:

> prova il flusso col cliente di esempio: crea il calendario e mostrami il link

## 10. Routine automatiche

Segui `routines/README.md` (5 minuti, si fa anche dal telefono).

## 11. Primo cliente vero (pilota)

> nuovo cliente: La Bolla Hair Spa, Borgo a Mozzano, beauty, 3 post e 3 story a settimana

Poi un mese di prova con lui solo, prima di aggiungere gli altri. Il cliente di esempio (`clienti/esempio-bistrot`) si può cancellare quando non serve più.
