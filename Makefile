.PHONY: validate test pipeline

validate:
	python -m py_compile 04_filter_quality.py 05_run_pipeline.py 13_city_guard.py 14_evidence_gate.py 15_run_pipeline_guarded.py
	python 15_run_pipeline_guarded.py
	python -m pytest -q

test:
	python -m pytest -q

pipeline:
	python 15_run_pipeline_guarded.py
