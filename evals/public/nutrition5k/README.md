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
system's own choices never became ground truth. Re-run the strict manifest validator after any future
label correction and create a new dataset version and split lock rather than mutating published results.
