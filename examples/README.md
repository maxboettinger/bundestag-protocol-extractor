# Bundestag Protocol Extractor Examples

This directory contains example Jupyter notebooks that demonstrate how to work with the Bundestag Protocol Extractor in various data science workflows.

## Available Examples

1. **data_science_workflow.ipynb**: Comprehensive example showing how to work with extracted speech data, including:
   - Loading and exploring the data structure
   - Filtering based on extraction quality
   - Generating quality visualizations
   - Analyzing speech data by party and other attributes
   - Creating integrated datasets for analysis

## Requirements

To run these examples, you'll need:

1. A Python environment with Jupyter installed
2. The Bundestag Protocol Extractor package installed
3. Data files in CSV format (generated by the extractor)

## Getting Started

1. Install Jupyter if you haven't already:
   ```
   pip install jupyter
   ```

2. Install matplotlib and seaborn for visualizations:
   ```
   pip install matplotlib seaborn
   ```

3. Run Jupyter:
   ```
   jupyter notebook
   ```

4. Open the desired notebook and run the cells to see the examples in action

## Data Files

The notebooks expect to find CSV data files in the `output` directory (at the same level as the examples directory). If your data is in a different location, you'll need to adjust the `data_dir` parameter in the notebook.

## Creating Your Own Examples

Feel free to use these examples as starting points for your own analysis. You can:

1. Copy and modify the existing notebooks
2. Create new notebooks that focus on specific aspects of the data
3. Extend the analysis with additional visualizations or metrics

If you create useful examples that might benefit others, consider contributing them back to the project!