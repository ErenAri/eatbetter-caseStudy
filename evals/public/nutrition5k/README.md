# Nutrition5k 12-dish public secondary subset

This directory contains a fixed 12-dish subset of Google Research's Nutrition5k dataset: 9 dishes
from the official RGB training split and 3 from the official RGB test split. It is a **secondary public
benchmark**, not a replacement for EatBetter's missing product-specific smartphone-photo dataset.

Nutrition5k contains real cafeteria dishes captured with a custom scanning rig, published ingredient
masses, and dish-level calories/macronutrients. The capture setup differs materially from an ordinary
single phone photo. Ingredient metadata also does not guarantee that every recipe ingredient is
visually separable. Those limitations must accompany every result.

The dataset is released by Google Research under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Source: [google-research-datasets/Nutrition5k](https://github.com/google-research-datasets/Nutrition5k).
Please cite:

> Thames, Q., Karpur, A., Norris, W., Xia, F., Panait, L., Weyand, T., & Sim, J. (2021).
> Nutrition5k: Towards Automatic Nutritional Understanding of Generic Food. CVPR 2021.

`build_subset.py` reproducibly downloads only the selected official overhead RGB images, validates the
official train/test membership, copies published decimal-safe mass/nutrition labels, and records file
hashes and source URLs. It does not download the 181.4 GB archive.

Visible-component labels were manually reviewed before model execution. USDA mappings were separately
reviewed before model execution: 30 item instances are `VERIFIED` and four are `UNMAPPABLE`; the
system's own choices never became ground truth.

## Evaluation-contract versioning

`manifest.json`, `sources.json`, and `split_lock.json` are the frozen `nutrition5k-public-secondary-v1`
artifacts used for the already-recorded historical development/holdout evaluation. They must not be
rewritten in place after observing those results.

The corrected evaluation contract is versioned separately as `nutrition5k-public-secondary-v2`.
Running `build_subset.py` now writes `manifest_v2.json` and `sources_v2.json` while leaving the v1
artifacts untouched. V2 adds two ground-truth facts that Nutrition5k's published per-ingredient metadata
supports:

- `hidden_truth_complete=true`, meaning absence may be graded as `NO` only for conservative atomic
  hidden-ingredient hypotheses that do not overlap another recorded hidden label.
- `calories_kcal` for measured hidden ingredients, allowing count-based hidden recall and
  calorie-weighted hidden coverage to be reported separately without inventing a materiality threshold.

Create a new split lock for v2 after generating the manifest. Because the three original holdout dishes
have already been observed, v2 development data may be used for tuning but those same three dishes must
not be described as a new untouched holdout. A future final holdout requires previously unseen cases.

Re-run the strict manifest validator after any future label correction and create a new dataset version
and split lock rather than mutating published results.
