# Confronto Rizzo Flow / Gemini 3.5 Flash-Lite / Liquid AI d1 / CLM-8B

Una pagina in italiano per confrontare la classificazione locale di [Rizzo Flow](https://github.com/Rizzo-AI-Academy/rizzo-flow) con **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`), **Liquid AI d1** e **[CLM-v0.1-8B](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B)** tramite il suo servizio ufficiale. Inserisci domanda, eventuale contesto testuale, file e classi possibili. Per ogni approccio vedi classificazione, tempo e costo API. Le chiamate partono in parallelo e ogni risultato compare appena disponibile.

## Uso del confronto

1. Scrivi la domanda o scegli Ticket, Sentiment o Documenti.
2. Aggiungi il contesto testuale e/o allega file.
3. Imposta da 2 a 25 classi, con nome e descrizione opzionale. Tutti i modelli possono astenersi con “Dati insufficienti”, se l'opzione è selezionata.
4. Inserisci la API key nel campo **Impostazioni Gemini**. Ottienila da [Google AI Studio](https://aistudio.google.com/apikey). Seleziona il piano a pagamento o gratuito effettivamente associato alla chiave.
5. Inserisci la chiave in **Impostazioni Liquid AI**, ottenuta da [Liquid Console](https://console.liquid.ai) → Dashboard → API Keys. Scegli `d1` oppure `d1:free`, se disponibile per il tuo account. I nomi provengono rispettivamente dall'[annuncio ufficiale d1](https://www.liquid.ai/blog/d1-decision-model) e dalla [guida ufficiale](https://docs.liquid.ai/guides/decision-model-guide). Non viene eseguito alcun fallback automatico.
6. In **Impostazioni CLM**, configura l'URL base di `clm-serve` (default `http://127.0.0.1:8700`), la chiave facoltativa e la modalità costo. Usa **Verifica servizio CLM** per controllare server, encoder e disponibilità di `clm-latest`.
7. Premi **Confronta i modelli**. Puoi impostare anche solo una delle due chiavi cloud; se CLM non è avviato la scheda mostra **Servizio non disponibile**, senza classificazioni simulate.

Per Gemini, Liquid AI e CLM puoi premere **Salva su questo browser** nelle rispettive impostazioni: la chiave viene conservata in `localStorage`, non cifrata, e ripristinata dopo il reload o la riapertura nello stesso profilo browser e allo stesso indirizzo/porta della demo. Per CLM viene salvato anche l'URL associato. **Rimuovi chiave** cancella la chiave dalla pagina e dalla memoria locale; non revoca la chiave presso il provider. Modificare il campo non aggiorna il valore salvato finché non premi nuovamente Salva. Senza salvataggio la chiave rimane solo nella pagina fino alla chiusura o al reload. La UI segnala eventuali errori se il browser impedisce la memorizzazione.

Le chiavi non sono incluse nei JSON di dettaglio né conservate in file dal backend, e vengono inviate al backend locale in header separati. Da lì vengono usate nell'header `x-goog-api-key` di Google o `Authorization: Bearer` di Liquid. La pagina informa che il confronto invia domanda, contesto e testo estratto dai file ai servizi per cui è presente una chiave. I file non vengono conservati dalla demo. Senza chiave, Rizzo continua a funzionare e la relativa scheda cloud compare come “Da configurare”. Nessun fallback a modelli diversi.

**Allegati:** TXT, Markdown, CSV, JSON, TSV, LOG in UTF-8, DOCX e PDF con testo selezionabile. Il testo viene estratto localmente una volta e fornito identico a tutti i modelli; non si usano le capacità multimodali dei servizi cloud. Immagini, scansioni, OCR e significato del layout non sono supportati. Massimo 5 file, 5 MB ciascuno, 10 MB totali e 32.000 caratteri complessivi tra domanda e contesto. Nessun troncamento silenzioso. Il contesto Rizzo è di 8.192 token: se lo supera la scheda locale restituisce un errore, mentre gli altri servizi possono comunque completare.

**Tempi:** misurati separatamente nel backend, prima della chiamata e fino alla risposta validata. Includono la coda locale e il viaggio di rete verso le API. Estrazione/preparazione degli allegati è comune, esclusa dai quattro tempi e mostrata separatamente. Il controllo preliminare CLM `/health` è escluso dalla classificazione e riportato come `health_check_ms`; se fallisce non viene avviata la classificazione e tempo/costo restano non disponibili. Il modello locale è già caricato prima delle misure. Un singolo confronto non è un benchmark statistico; carico della macchina, rete e cache del runtime influenzano i risultati.

**Costi:** Rizzo mostra $0 di costo API, escludendo hardware ed energia. Gemini mostra una **stima in USD**, calcolata sui token effettivamente riportati in `usageMetadata`. Le [tariffe Google standard](https://ai.google.dev/gemini-api/docs/pricing), verificate l'8 ottobre 2026, sono $0,30/M token input, $0,03/M input in cache e $2,50/M output, inclusi i token di ragionamento. Formula: `(input_non_cached * 0.30 + input_cached * 0.03 + (output + thinking) * 2.50) / 1_000_000`. Il totale token viene usato anche per verificare che il ragionamento non sia escluso. Nessun tool, grounding, retry automatico o cache esplicita. Il piano gratuito è una scelta dichiarata dall'utente, non verificabile dalla risposta API; il JSON mostra anche il costo equivalente a pagamento. Se mancano i contatori o la chiamata fallisce senza una risposta di consumo, il costo compare come non determinabile, mai come un falso zero. La fattura Google rimane il riferimento effettivo.

**Liquid:** usa l'API diretta `POST https://api.liquid.ai/decisions/v1/systemone` con una domanda `Choice`, lo stesso `state` e le classi nel campo `criteria`. Mostra probabilità e confidenza restituite dal servizio. Per `d1` stima `usage.input_tokens * 0.04 / 1_000_000` USD, senza costo di output, secondo l'annuncio ufficiale verificato l'8 ottobre 2026. Per `d1:free` mostra $0 solo se il consumo viene riportato; in caso di errore senza consumo il costo resta sconosciuto. Nessun retry automatico. I test dell'integrazione usano fixture: la verifica autenticata richiede la chiave dell'utente nel frontend.

Rizzo restituisce le probabilità delle classi, non calibrate sul tuo caso d'uso. Liquid dichiara probabilità calibrate: ciò non garantisce la correttezza di ogni decisione. Gemini genera solo un JSON vincolato con l'ID di una classe (thinking `MINIMAL`, temperatura 0); non si mostrano probabilità inventate. La demo segnala se i risultati completati coincidono e se il confronto è parziale, senza assumere che quello concorde sia corretto.

## Avvio su Windows

Prerequisiti: [Git](https://git-scm.com/downloads) e [uv](https://docs.astral.sh/uv/getting-started/installation/). Python 3.11 viene gestito da uv.

Dalla cartella del progetto, in PowerShell:

```powershell
.\start.ps1
```

Apri **http://127.0.0.1:8017** quando il terminale indica che il server è pronto. Arresta con **Ctrl+C**. Lo script installa anche `pypdf==6.1.1` per estrarre i PDF.

Il primo avvio clona il repository, installa le dipendenze bloccate da `uv.lock` e scarica il modello fine-tuned **4B Q4_K_M (~2,6 GB)** e llama.cpp (dimensione variabile con il runtime, fino a circa 570 MB con CUDA). I file restano in `.runtime/rizzo-flow`; i download già completati sono riutilizzati e quelli interrotti sono ripresi dal downloader ufficiale. La GPU viene scelta automaticamente, se disponibile; su CPU le decisioni possono richiedere più tempo.

Se la policy PowerShell blocca lo script, eseguilo senza cambiare la policy permanente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Avvii successivi, evitando anche la verifica dei download:

```powershell
.\start.ps1 -SkipDownload
```

Altre opzioni:

```powershell
# Modello più piccolo (~1,8 GB), meno accurato
.\start.ps1 -Size 1.7b -Quant q8_0

# Forza il runtime CPU e l'inferenza CPU
.\start.ps1 -Runtime cpu -Device cpu

# Cambia porta
.\start.ps1 -Port 8020 -SkipDownload
```

Usa `-SkipDownload` solo dopo avere scaricato la combinazione di modello, quantizzazione e runtime selezionata. Ogni combinazione viene conservata separatamente.

## API originali senza interfaccia

Con il server avviato, da un secondo terminale nella cartella del progetto:

```powershell
$ticketBody = Get-Content .\web\ticket.json -Raw -Encoding UTF8
Invoke-RestMethod http://127.0.0.1:8017/v1/decisions `
    -Method Post -ContentType 'application/json; charset=utf-8' `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($ticketBody)) |
    ConvertTo-Json -Depth 20
```

Disponibili anche `/health`, `/docs`, `/playground` e l'endpoint compatibile `/v1/systemone` del progetto originale.

## File e comportamento

- `app.py`: carica il modello una volta e aggiunge le API di confronto all'app FastAPI ufficiale. Ascolta solo su `127.0.0.1`.
- `comparison.py`: validazione del caso, estrazione file, classificazione Rizzo, richieste Gemini e Liquid REST e calcolo costi.
- `web/`: HTML, CSS e JavaScript senza dipendenze frontend; gli input sono configurabili dalla pagina. `ticket.json` mantiene l'esempio delle API originali.
- `start.ps1`: prepara e avvia l'ambiente locale. Revisione upstream fissata a `b9ba007ee4d2928bbab5b1d8bfe9009c3696b6de`; nessuna modifica al codice originale.

Nuove API: `GET /api/config`, `POST /api/prepare`, `POST /api/classify/rizzo` e `POST /api/classify/gemini`. Quest'ultima riceve `{ "case": <caso_preparato>, "billing_tier": "paid" }` e la chiave nell'header `X-Gemini-API-Key`. Nessun risultato simulato nell'app. I JSON delle nuove API non vengono messi in cache e le richieste browser da altre origini vengono rifiutate.

Liquid: `POST /api/classify/liquid`, body `{ "case": <caso_preparato>, "model": "d1" }`, chiave nell'header `X-Liquid-API-Key`. Modelli ammessi: `d1`, `d1:free`.

## Collegare CLM-v0.1-8B

La demo integra il contratto ufficiale `POST /v1/systemone`, `Choice`, modello `clm-latest`, temperatura 1. Il servizio deve caricare il checkpoint **Contrastive-LM/CLM-v0.1-8B**, con encoder **Qwen/Qwen3-8B** last-token pooled e le due projection heads ufficiali. Non si usa Qwen generativo, `qwen-raw` o un altro modello come sostituto. L'alias `clm-latest` viene verificato nella risposta; il servizio ufficiale non espone l'hash del checkpoint tramite health, perciò chi lo gestisce deve configurare il checkpoint corretto.

### Servizio locale Windows

È incluso un runner CPU per Windows, senza vLLM o GPU NVIDIA. Installa le dipendenze in `.runtime/clm-local/.venv`, scarica **Qwen/Qwen3-8B** (~16 GB) e le heads ufficiali (~75 MB), quindi avvia l'API sulla porta 8700:

```powershell
# Prima installazione e avvio (download riprendibile)
.\start-clm.ps1 -Install

# Avvii successivi, senza download
.\start-clm.ps1
```

Attendi **CLM pronto**. Nell'app lascia `http://127.0.0.1:8700`, scegli **Autogestito** e premi **Verifica servizio CLM**. Una volta installato, `start.ps1` avvia anche CLM in background se non è già attivo e attende il caricamento prima di caricare Rizzo, per limitare il picco di memoria; `-SkipCLM` lo disabilita. I log sono in `.runtime/clm-local/server.log` e `server-error.log`. Ctrl+C arresta anche il processo CLM avviato dallo script, ma non un servizio già attivo separatamente.

`clm_local.py` usa `AutoModel` Transformers, testo senza chat template, ultimo token e normalizzazione L2. Il motore e le due heads sono quelli del codice CLM ufficiale, revisioni bloccate negli script. Per rendere l'inferenza praticabile su CPU AVX2, i layer lineari dell'encoder sono quantizzati dinamicamente a **INT8**, con embedding/attivazioni FP16 e heads FP32. La scheda espone questo runtime: la quantizzazione può modificare probabilità e decisioni rispetto all'encoder BF16 su GPU. Non viene eseguita generazione o sostituzione con un classificatore differente. Caricamento e conversione avvengono prima che `/health` indichi pronto e sono esclusi dal tempo di classificazione. Il limite è **8192 token per testo**, con errore esplicito invece di troncamento. La cache riutilizza stati e candidati identici; ripetere esattamente il caso può essere molto più veloce.

Serve spazio su disco per circa 17 GB di pesi e dipendenze, fino a circa 34 GB durante il download a blocchi (verificato tramite SHA-256), e RAM sufficiente per il caricamento iniziale a 16 bit (~16 GB più overhead). Il runtime PyTorch/oneDNN può mantenere copie dei pesi impacchettati: nella verifica su questo PC il processo CLM occupava circa 15 GB, oltre alla memoria di Rizzo. La quantizzazione migliora la velocità CPU, ma non equivale a un benchmark del servizio GPU upstream. Verificato il servizio reale l'11 ottobre 2026: il test HTTP ha classificato il ticket come **Accesso**, con **12,8 s** e **$0 API**, escludendo caricamento e verifica preliminare; questa singola misura non è una media di benchmark.

### Servizio remoto o vLLM

Quickstart sul **server CLM**, in un ambiente separato compatibile con vLLM, basato sul [codice ufficiale](https://github.com/Contrastive-LM/CLM) verificato alla revisione `d5f9ef0fd9bde185df0ceaad4f4ecc6cfe8c34f6`:

```sh
pip install contrastive-lm
# Terminale 1: encoder Qwen3-8B, embeddings con runner pooling
vllm serve Qwen/Qwen3-8B --served-model-name qwen3-8b --runner pooling --max-model-len 8192 --port 8090
# Terminale 2: CLM con lo stesso limite; heads ufficiali scaricate al primo avvio
clm-serve --host 127.0.0.1 --port 8700 --max-tokens 8192
```

L'eventuale `CLM_API_KEY` viene configurata sul server; inserisci la stessa chiave nel frontend della demo. L'URL base accetta HTTP su loopback oppure HTTPS remoto, anche sotto un prefisso, senza credenziali/query/frammenti. Le richieste partono dal backend locale: non serve abilitare CORS sul server CLM. I redirect non vengono seguiti per evitare di inoltrare la chiave a un'altra destinazione. Non esporre l'encoder senza le protezioni del tuo hosting.

**Limiti del confronto:** tutti ricevono gli stessi dati di domanda, contesto, allegati e classi. CLM rende lo stato e le descrizioni come testo tramite la propria API. Il quickstart upstream usa 2048 token e tronca testi più lunghi; nell'esempio sopra entrambi i limiti sono 8192. Il limite non è esposto da `/health`, quindi la demo non può verificarlo né garantire che un server configurato con un limite inferiore non tronchi. Adegua il limite alla lunghezza delle tue richieste e alla memoria disponibile. Le probabilità CLM sono softmax relative ai candidati, non certezza calibrata; cache di stati e azioni può ridurre latenza e token riportati.

**Costo CLM:** autogestito dichiarato → $0 API solo dopo una risposta del servizio, escludendo hardware, energia e hosting; tariffa non nota → costo non determinabile; tariffa per token inserita → stima `usage.input_tokens * tariffa / 1_000_000`. Non esiste una tariffa commerciale implicita nella demo. La cache può modificare i token riportati: applica questa stima solo se il tuo hosting fattura quel contatore. La chiave CLM passa negli header `X-CLM-API-Key` (locale) e `Authorization: Bearer` (servizio); il salvataggio facoltativo da UI avviene solo nel browser, insieme all'URL, senza includerla nei JSON dei risultati.

API aggiunte: `POST /api/clm/health` con `{ "base_url": "http://127.0.0.1:8700" }`; `POST /api/classify/clm` con `{ "case": <caso_preparato>, "base_url": "http://127.0.0.1:8700", "billing_mode": "self_hosted", "input_per_million_usd": null }`. Modalità costo: `self_hosted`, `unknown`, `per_token`. `/health` del servizio ufficiale deve indicare encoder raggiungibile e modello disponibile; modalità mock viene rifiutata.

## Verifica della demo

Controlli locali di contratti, estrazione TXT/PDF/DOCX, schemi Gemini e Liquid, risposte non valide, gestione chiavi e calcolo costi. I test cloud usano risposte fixture, senza chiamate fatturabili:

```powershell
.\.runtime\rizzo-flow\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Il controllo HTTP seguente usa Rizzo reale e richiede il server avviato. Verifica la pagina, le API originali e il nuovo confronto, compresi Gemini e Liquid senza chiave:

```powershell
.\.runtime\rizzo-flow\.venv\Scripts\python.exe .\smoke_test.py

# Richiede una classificazione CLM reale, non accetta il servizio non disponibile
.\.runtime\rizzo-flow\.venv\Scripts\python.exe .\smoke_test.py --require-clm

# Verifica numerica INT8/FP16 con un piccolo Qwen3, nell'ambiente separato CLM
.\.runtime\clm-local\.venv\Scripts\python.exe -m unittest discover -s tests -p test_clm_encoder.py -v
```
