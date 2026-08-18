# Development experiments

Create one immutable directory per measured development change. Record `experiment_id`, date,
configuration snapshot, prompt/model versions, thresholds, one change description, before metrics,
after metrics, and the failure class motivating the change. Never tune on the holdout and never
overwrite a versioned prompt.
