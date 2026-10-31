.PHONY: install seed run test serve bot demo reset
install: ; pip install -r requirements.txt
seed:    ; python -m closecrew seed
run:     ; python -m closecrew run
test:    ; python -m pytest -q
serve:   ; uvicorn app.server:app --reload --port 8000
bot:     ; python -m closecrew.telegram_bot
reset:   ; python -m closecrew reset && python -m closecrew seed
demo: reset run test
