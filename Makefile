.PHONY: test demo serve lint

test:
	pytest -q

demo:
	python -m supply_chain demo

serve:
	python -m supply_chain serve

lint:
	python -m compileall -q src tests examples
