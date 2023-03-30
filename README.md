# Cryosparc-tools-scripts
This repository contains a set of scripts for processing CryoEM data using the [CryoSPARC tools](https://tools.cryosparc.com/intro.html) python library.

## TO DO list:
- [X] Threshold filtering
- [O] Visulize particles in micrographs

# Usage
## crYOLO particle picking
Particle picking scripts inspired from https://tools.cryosparc.com/examples/cryolo.html.

### crYOLO_particlepicker.py
`crYOLO_particlepicker.py` script enables you to perform crYOLO particle picking in CryoSPARC. The script takes curated exposures and predicts particle locations. Particle picks can then be filtered by threshold in an `Inspect Picks` job.

The script takes the following command-line arguments:

- `project` - Name of the project to run the job in.
- `workspace` - Name of the workspace to run the job in.
- `curate_exposures_job_id` - ID of the job that curated the micrographs.
- `box_size` - Box size for particle picking (in Angstroms).
- `model_path` - Path to crYOLO model

Here is a sample command:
``` 
python crYOLO_particlepicker.py P1 W1 J3 110 path_to_model.h5 
```

### crYOLO_trainedpicker.py
`crYOLO_trainedpicker.py` script enables you to train crYOLO particle picking model and use it to pick particles in CryoSPARC.