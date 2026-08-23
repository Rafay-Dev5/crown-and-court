validate:

	python -m engine.validate



test:

	pytest -q



train:

	python -m training.trainer --episodes 200 --start-episode 0



train-gpu:

	python -m training.trainer --episodes 10000 --start-episode 0 --benchmark-every 2500 --seed 7



train-fresh-10k: train-gpu

train-scale-20k:
	python -m training.trainer --episodes 20000 --start-episode 0 --benchmark-every 5000 --seed 7

train-quick:

	python -m training.trainer --episodes 200 --start-episode 0 --seed 7



sweep:

	python -m analytics.sweeps --config configs/balance.yaml --games 100



kingmaker:

	python -m analytics.kingmaker_test --games 100



report:

	python -m analytics.report_generator

	python -m analytics.export_viewer_balance



export-balance:

	python -m analytics.export_viewer_balance



export-rules:

	python -m scripts.export_rules_cards



export-proxies:

	python -m scripts.export_playtest_proxies



balance:

	python -m analytics.auto_tune --games 100 --kingmaker-games 200



signoff:

	python -m analytics.signoff_compare --games-standard 100 --games-prd 385 --no-tune



diagnostics:

	python -m analytics.diagnostics



nerf-outliers:

	python scripts/nerf_outliers.py



manifest:

	python -c "from engine.cards import write_manifest; print(write_manifest())"



benchmark:

	python -m training.benchmark --config configs/training.yaml --games 100



resize-decks:

	python scripts/resize_unique_decks.py



expand-decks:

	python scripts/expand_deck_designs.py



tune-shield:

	python scripts/tune_shield_balance.py



replace-stubs:

	python scripts/replace_stub_cards.py



card-workflow:

	python scripts/card_workflow.py



card-workflow-quick:

	python scripts/card_workflow.py --quick



card-diagnose:

	python -m analytics.card_balance



card-tune:

	python -m analytics.card_balance --tune



save-baseline:

	python -m analytics.card_balance --save-baseline --games 385



param-grid:

	python -m analytics.parameter_grid --config configs/parameter_grid.yaml



param-grid-report:

	python -m analytics.report_generator --sweep game_logs/parameter_grid_results.json



.PHONY: validate test train train-gpu train-fresh-10k train-scale-20k train-quick sweep report kingmaker balance signoff nerf-outliers export-balance manifest diagnostics benchmark resize-decks expand-decks tune-shield replace-stubs card-workflow card-workflow-quick card-diagnose card-tune save-baseline param-grid param-grid-report


