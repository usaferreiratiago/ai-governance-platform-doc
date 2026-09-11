setup:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

run:
	streamlit run streamlit_app/app.py

benchmarks:
	python evaluation/run_benchmarks.py

init-db:
	python -m scripts.init_db