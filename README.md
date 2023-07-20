# Cryosparc-tools-scripts
This repository contains a set of scripts for processing CryoEM data using the [CryoSPARC tools](https://tools.cryosparc.com/intro.html) python library.

## Contents
- [crYOLO particle picking](#cryolo-particle-picking)
    - [crYOLO_particlepicker.py](#cryolo_particlepickerpy)
    - [crYOLO_trainedpicker.py](#cryolo_trainedpickerpy)
- [cryodrgn](#cryodrgn)
    - [cryodrgn_trainer_downsampled.py](#cryodrgn_trainer_downsampledpy)

# Scripts:
## crYOLO particle picking
Particle picking scripts inspired from https://tools.cryosparc.com/examples/cryolo.html.

### <b>crYOLO_particlepicker.py</b>
`crYOLO_particlepicker.py` script enables you to perform crYOLO particle picking in CryoSPARC. 

The script takes `Curated Exposures` and predicts particle locations. Particle picks can then be filtered by threshold in an `Inspect Picks` job.

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

---

### <b>crYOLO_trainedpicker.py</b>
`crYOLO_trainedpicker.py` script enables you to train crYOLO particle picking model and use it to pick particles in CryoSPARC. 

The script takes in picked particles for training, usually from `Select 2D` job. Another importatnt input is the `Exposure Sets` job with split micrographs for training and testing. Particle picks can then be filtered by threshold in an `Inspect Picks` job.

> **Note:** (1000/3000 micrographs split takes about 8 hours for training and prediction)

The script takes the following command-line arguments:
- `project` - Name of the project to run the job in.
- `workspace` - Name of the workspace to run the job in.
- `training_particles_job_id` - ID of job with picked particles for training (usually `Select 2D` job)
- `exposure_sets_job_id` - ID of exposure sets tool job, used to split micrographs
- `box_size` - Box size for particle picking (in Angstroms).
- `model_path` - Path to crYOLO model

Here is a sample command:
``` 
python crYOLO_trainedpicker.py P1 W1 J3 J5 110
```

---

## cryodrgn
Script for running cryodrgn in cryosparc.

### <b>cryodrgn_trainer_downsampled.py</b>
`cryodrgn_trainer_downsampled.py` script enables you to train cryodrgn model and do basic analysis in CryoSPARC.

To prepare the inputs, run C1 `Homogenous Refinement` job and perform `Downsample` on selected particle set (usually box size of 128-256pix).

> **Note:** For now, results can be found in job directory

The script takes the following command-line arguments:
- `project` - Name of the project to run the job in.
- `workspace` - Name of the workspace to run the job in.
- `refinement_job_id` - ID of the C1 `Homogeneous Refinement` job
- `downsample_job_id` - ID of the downsample particle job
