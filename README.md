# Confronto Rizzo Flow / Gemini 3.5 Flash-Lite / Liquid AI d1

Una pagina in italiano per confrontare la classificazione locale di [Rizzo Flow](https://github.com/Rizzo-AI-Academy/rizzo-flow) con **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`) e **Liquid AI d1**, un modello di decisione cloud. Inserisci domanda, eventuale contesto testuale, file e classi possibili. Per ogni approccio vedi classificazione, tempo e costo API. Le chiamate partono in parallelo e ogni risultato compare appena disponibile.

## Uso del confronto

1. Scrivi la domanda o scegli Ticket, Sentiment o Documenti.
2. Aggiungi il contesto testuale e/o allega file.
3. Imposta da 2 a 25 classi, con nome e descrizione opzionale. Tutti i modelli possono astenersi con “Dati insufficienti”, se l'opzione è selezionata.
4. Inserisci la API key nel campo **Impostazioni Gemini**. Ottienila da [Google AI Studio](https://aistudio.google.com/apikey). Seleziona il piano a pagamento o gratuito effettivamente associato alla chiave.
5. Inserisci la chiave in **Impostazioni Liquid AI**, ottenuta da [Liquid Console](https://console.liquid.ai) → Dashboard → API Keys. Scegli `d1` oppure `d1:free`, se disponibile per il tuo account. I nomi provengono rispettivamente dall'[annuncio ufficiale d1](https://www.liquid.ai/blog/d1-decision-model) e dalla [guida ufficiale](https://docs.liquid.ai/guides/decision-model-guide). Non viene eseguito alcun fallback automatico.
6. Premi **Confronta i modelli**. Puoi impostare anche solo una delle due chiavi cloud.

Le API key rimangono nella pagina fino alla chiusura o al reload: non sono salvate in localStorage, cookie o file, non sono incluse nei JSON di dettaglio e vengono inviate al backend locale in header separati. Da lì vengono usate nell'header `x-goog-api-key` di Google o `Authorization: Bearer` di Liquid. La pagina informa che il confronto invia domanda, contesto e testo estratto dai file ai servizi per cui è presente una chiave. I file non vengono conservati dalla demo. Senza chiave, Rizzo continua a funzionare e la relativa scheda cloud compare come “Da configurare”. Nessun fallback a modelli diversi.

**Allegati:** TXT, Markdown, CSV, JSON, TSV, LOG in UTF-8, DOCX e PDF con testo selezionabile. Il testo viene estratto localmente una volta e fornito identico a tutti i modelli; non si usano le capacità multimodali dei servizi cloud. Immagini, scansioni, OCR e significato del layout non sono supportati. Massimo 5 file, 5 MB ciascuno, 10 MB totali e 32.000 caratteri complessivi tra domanda e contesto. Nessun troncamento silenzioso. Il contesto Rizzo è di 8.192 token: se lo supera la scheda locale restituisce un errore, mentre gli altri servizi possono comunque completare.

**Tempi:** misurati separatamente nel backend, prima della chiamata e fino alla risposta validata. Includono la coda locale e, per Gemini e Liquid, il viaggio di rete verso il servizio. Estrazione/preparazione degli allegati è comune, esclusa dai tre tempi e mostrata separatamente. Il modello locale è già caricato prima delle misure. Un singolo confronto non è un benchmark statistico; carico della macchina, rete e cache del runtime influenzano i risultati.

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

## Verifica della demo

Controlli locali di contratti, estrazione TXT/PDF/DOCX, schemi Gemini e Liquid, risposte non valide, gestione chiavi e calcolo costi. I test cloud usano risposte fixture, senza chiamate fatturabili:

```powershell
.\.runtime\rizzo-flow\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Il controllo HTTP seguente usa Rizzo reale e richiede il server avviato. Verifica la pagina, le API originali e il nuovo confronto, compresi Gemini e Liquid senza chiave:

```powershell
.\.runtime\rizzo-flow\.venv\Scripts\python.exe .\smoke_test.py
```
