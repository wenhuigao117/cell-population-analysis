.PHONY: setup pipeline dashboard

setup:
	pip install -r requirements.txt

pipeline:
	python3 pipeline.py

dashboard:
	python3 app.py