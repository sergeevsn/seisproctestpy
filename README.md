# <span style="color: #2c5f2d;">SeisProcTestPy</span>
### Version 1.0

A Python-based tool for testing processing workflows on SEG-Y format seismic data.

![Preview of SeisProcTestPy](preview.jpg)

## Key Features:

- Import/export 2D seismic data in SEG-Y format

- Interactive visualization with customizable color maps and gain settings

- Parameter sweep testing for user-defined algorithms

- Flexible integration: Supports any Python library function that accepts a 2D ndarray + parameters

- A/B comparison between original and processed data

- Mouse-driven zoom:

Left-click + drag to zoom in

Right-click to reset view

- Saving figures to mp4 movie

- Application of the chosen procedure/parameter set to a set of SEG-Y files in specified folder

## Limitations:

- Full-trace loading: Designed for 2D seismic sections or single gathers (not optimized for large 3D volumes)

- Performance constraints: Python/PyQt5 may limit UI responsiveness with very large files

- All testing results are kept in memory, so not too much variants please!

- JSON parameter editing: Less intuitive than GUI-based configuration

## Notes:
- Input data is auto-scaled to [0, 1] before processing and reverted to original range for display

# Tech Stack:
- PyQt5 (GUI framework)

- Matplotlib (visualization)

- NumPy (array processing)

- Segyio (SEG-Y I/O)

- Scikit-learn (MinMaxScaler for normalization)

- imageio-ffmpeg (Figures to movie)

```
pip install --upgrade matplotlib PyQt5 numpy sklearn segyio imageio imageio-ffmpeg
```


## Usage:

```
python main.py
```

<sub>© 2025 Сергей Сергеев</sub>
