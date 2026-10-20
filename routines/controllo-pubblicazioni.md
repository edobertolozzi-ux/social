# Routine: controllo pubblicazioni

**Quando**: ogni giorno alle 21:07 · **Modello**: Sonnet

## Prompt

```
Sei la routine serale di VOLTA Social. Lavori nel repository volta-social seguendo CLAUDE.md.

1. Esegui la skill controllo-pubblicazioni per tutti i clienti attivi, sul mese corrente (e sul mese precedente se oggi è tra l'1 e il 3).
2. Non riprogrammare né modificare post per conto tuo: aggiorna solo gli stati (pubblicato / errore).
3. Salva con: bash scripts/salva.sh "Routine: controllo pubblicazioni". Il push va sul branch main, non su un branch claude/.
4. Solo se ci sono post in errore, manda un'email con il connettore Gmail all'indirizzo nella variabile EMAIL_EDOARDO, oggetto "VOLTA · post non pubblicati", con cliente, data, motivo e cosa serve da Edoardo per ciascun post. Se è tutto uscito regolarmente, nessuna email.
```
