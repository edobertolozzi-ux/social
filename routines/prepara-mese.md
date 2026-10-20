# Routine: prepara il mese

**Quando**: ogni giorno alle 02:07 · **Modello**: Opus

## Prompt

```
Sei la routine notturna di VOLTA Social. Lavori nel repository volta-social seguendo CLAUDE.md.

1. Guarda la data di oggi (fuso Europe/Rome). Se il giorno del mese NON è tra 20 e 25, scrivi "Fuori finestra, niente da fare" e termina subito senza fare altro.
2. Esegui la skill prepara-mese in modalità routine per il MESE PROSSIMO, per al massimo 4 clienti attivi che non hanno ancora il piano (o lo hanno ancora in bozza), in ordine alfabetico. Gli altri li farai le notti successive.
3. Non programmare e non approvare niente: questa routine prepara solo le bozze.
4. Salva tutto con: bash scripts/salva.sh "Routine: bozze del mese prossimo". Il push va fatto sul branch main, non su un branch claude/.
5. Se hai preparato almeno un piano, manda un'email con il connettore Gmail all'indirizzo nella variabile d'ambiente EMAIL_EDOARDO, oggetto "VOLTA · bozze pronte da approvare": per ogni cliente una riga (post pronti, post da correggere, materiali da chiedere al cliente) e il link CALENDARIO_URL. Se non hai preparato niente perché erano già tutti pronti, non mandare email.
6. Se qualcosa non funziona (Drive, rete, script), non insistere: descrivi il problema in una riga nell'email.
```
