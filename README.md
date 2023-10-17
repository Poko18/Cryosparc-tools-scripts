# Cryosparc-tools-scripts
This repository contains a set of scripts for processing CryoEM data using the [CryoSPARC tools](https://tools.cryosparc.com/intro.html) python library.

## Contents
- [crYOLO particle picking](#cryolo-particle-picking)
    - [crYOLO_particlepicker.py](#cryolo_particlepickerpy)
    - [crYOLO_trainedpicker.py](#cryolo_trainedpickerpy)
- [cryodrgn](#cryodrgn)
    - [cryodrgn_trainer_downsampled.py](#cryodrgn_trainer_downsampledpy)
- [cs2star](#cs2star)
    - [cs2star_2Dparticles.py](#cs2star_2Dparticlespy)

# Scripts:
## crYOLO particle picking
Particle picking scripts inspired from https://tools.cryosparc.com/examples/cryolo.html.

### Installation
Create conda environment following the tutorial from the link above. But in short:
```
conda create -n cryolo -c conda-forge \
   python=3 numpy==1.18.5 \
   libtiff pyqt=5 wxPython=4.1.1 adwaita-icon-theme
conda activate cryolo
pip install -U pip
pip install nvidia-pyindex
pip install cryolo[c11] cryosparc-tools
```

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
Script for running [cryodrgn](https://github.com/zhonge/cryodrgn/tree/master) in cryosparc.

### Installation
Before use, create conda environment for cryodrgn and make sure pytorch is working on your GPU.
```
conda create --name cryodrgn python=3.9
conda activate cryodrgn
pip install cryodrgn
pip install cryosparc-tools
```

### <b>cryodrgn_trainer_downsampled.py</b>
`cryodrgn_trainer_downsampled.py` script enables you to train cryodrgn model and do basic analysis in CryoSPARC.

To prepare the inputs, run C1 `Homogenous Refinement` job and perform `Downsample` on selected particle set (usually box size of 128-256pix).

> **Note:** For now, results can be found in job directory

The script takes the following command-line arguments:
- `project` - Name of the project to run the job in.
- `workspace` - Name of the workspace to run the job in.
- `refinement_job_id` - ID of the C1 `Homogeneous Refinement` job
- `downsample_job_id` - ID of the downsample particle job

Here is a sample command:
``` 
python cryodrgn_trainer_downsampled.py P1 W1 J10 J11
```

## cs2star
Scripts using pyem (https://github.com/asarnow/pyem) in cryosparc.

TODO:
- [ ] input cryosparc job, run relion schema and output results back in cryosparc

### installation
Create pyem conda environment before use:
```
conda create -n pyem
conda activate pyem
conda install numpy scipy matplotlib seaborn numba pandas natsort
conda install -c conda-forge pyfftw healpy pathos
git clone https://github.com/asarnow/pyem.git
cd pyem
pip install --no-dependencies -e .
pip install cryosparc-tools
```

### cs2star_2Dparticles.py
`cs2star_2Dparticles.py` script enables you to directly prepare particles for Relion by just specifiying project, `Select 2D` job and path to relion projct folder.

> **Note:** Script does not create a job in CryoSparc. It just sources the paths an folders

The script takes the following command-line arguments:
- `project` - Name of the project with `2D select` job.
- `select2D_job_id` - ID of the `Select 2D` job.
- `relion_project_path` - Path to the RELION project

Here is a sample command:
```
python cs2star_2Dparticles.py P2 J12 path_to_relion_project
```