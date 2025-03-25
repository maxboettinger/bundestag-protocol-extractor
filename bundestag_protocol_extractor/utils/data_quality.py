"""
Data quality utilities for Bundestag Protocol Extractor.

This module provides tools for assessing, reporting, and visualizing
extraction quality for data science workflows.
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from bundestag_protocol_extractor.models.schema import PlenarProtocol, Speech
from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


class DataQualityReporter:
    """Class for generating and visualizing data quality reports."""

    def __init__(self, output_dir: Union[str, Path] = "output"):
        """
        Initialize the data quality reporter.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_quality_report(
        self,
        df_speeches: pd.DataFrame,
        protocol_metadata: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive quality report for speech extraction.

        Args:
            df_speeches: DataFrame containing speech data
            protocol_metadata: Optional DataFrame with protocol metadata

        Returns:
            Dictionary with quality metrics
        """
        total_speeches = len(df_speeches)

        if total_speeches == 0:
            return {
                "generated_at": datetime.now(),
                "total_speeches": 0,
                "error": "No speech data available for quality report",
            }

        # Get basic stats on extraction methods
        extraction_methods = df_speeches["extraction_method"].value_counts().to_dict()
        extraction_status = df_speeches["extraction_status"].value_counts().to_dict()

        # Get detailed percentage statistics
        method_percentages = (
            df_speeches["extraction_method"].value_counts(normalize=True) * 100
        ).to_dict()
        status_percentages = (
            df_speeches["extraction_status"].value_counts(normalize=True) * 100
        ).to_dict()

        # Calculate confidence statistics
        avg_confidence = float(df_speeches["extraction_confidence"].mean())
        median_confidence = float(df_speeches["extraction_confidence"].median())
        min_confidence = float(df_speeches["extraction_confidence"].min())
        max_confidence = float(df_speeches["extraction_confidence"].max())

        # Distribution by confidence tiers
        high_confidence = df_speeches[
            df_speeches["extraction_confidence"] >= 0.8
        ].shape[0]
        medium_confidence = df_speeches[
            (df_speeches["extraction_confidence"] >= 0.5)
            & (df_speeches["extraction_confidence"] < 0.8)
        ].shape[0]
        low_confidence = df_speeches[
            (df_speeches["extraction_confidence"] >= 0.2)
            & (df_speeches["extraction_confidence"] < 0.5)
        ].shape[0]
        very_low_confidence = df_speeches[
            df_speeches["extraction_confidence"] < 0.2
        ].shape[0]

        # Text quality metrics
        if "text" in df_speeches.columns:
            # Calculate text length statistics
            df_speeches["text_length"] = df_speeches["text"].str.len()
            avg_text_length = float(df_speeches["text_length"].mean())
            median_text_length = float(df_speeches["text_length"].median())
            min_text_length = int(df_speeches["text_length"].min())
            max_text_length = int(df_speeches["text_length"].max())

            # Count speeches with potentially truncated text
            truncated_count = df_speeches[
                df_speeches["text"].str.contains("EXTRACTION_FAILED")
            ].shape[0]
            truncated_percentage = (
                (truncated_count / total_speeches) * 100 if total_speeches > 0 else 0
            )

            # Calculate text length by extraction method
            text_length_by_method = {}
            for method in extraction_methods.keys():
                method_texts = df_speeches[df_speeches["extraction_method"] == method]
                if not method_texts.empty:
                    text_length_by_method[method] = {
                        "average": float(method_texts["text_length"].mean()),
                        "median": float(method_texts["text_length"].median()),
                        "min": int(method_texts["text_length"].min()),
                        "max": int(method_texts["text_length"].max()),
                    }
        else:
            avg_text_length = 0
            median_text_length = 0
            min_text_length = 0
            max_text_length = 0
            truncated_count = 0
            truncated_percentage = 0
            text_length_by_method = {}

        # Protocol-level statistics (if protocol metadata provided)
        protocol_stats = {}
        if protocol_metadata is not None and not protocol_metadata.empty:
            protocol_count = len(protocol_metadata)

            # Count protocols with speeches
            df_protocols_with_speeches = df_speeches["protocol_id"].nunique()

            # Calculate average speeches per protocol
            speeches_per_protocol = df_speeches.groupby("protocol_id").size()
            avg_speeches_per_protocol = float(speeches_per_protocol.mean())
            median_speeches_per_protocol = float(speeches_per_protocol.median())
            min_speeches_per_protocol = int(speeches_per_protocol.min())
            max_speeches_per_protocol = int(speeches_per_protocol.max())

            protocol_stats = {
                "total_protocols": protocol_count,
                "protocols_with_speeches": df_protocols_with_speeches,
                "protocols_without_speeches": protocol_count
                - df_protocols_with_speeches,
                "avg_speeches_per_protocol": avg_speeches_per_protocol,
                "median_speeches_per_protocol": median_speeches_per_protocol,
                "min_speeches_per_protocol": min_speeches_per_protocol,
                "max_speeches_per_protocol": max_speeches_per_protocol,
            }

        # Compile quality report
        report = {
            "generated_at": datetime.now(),
            "total_speeches": total_speeches,
            "extraction_methods": {
                "counts": extraction_methods,
                "percentages": method_percentages,
            },
            "extraction_status": {
                "counts": extraction_status,
                "percentages": status_percentages,
            },
            "confidence_metrics": {
                "average": avg_confidence,
                "median": median_confidence,
                "min": min_confidence,
                "max": max_confidence,
                "distribution": {
                    "high_confidence": high_confidence,
                    "high_confidence_percentage": (high_confidence / total_speeches)
                    * 100,
                    "medium_confidence": medium_confidence,
                    "medium_confidence_percentage": (medium_confidence / total_speeches)
                    * 100,
                    "low_confidence": low_confidence,
                    "low_confidence_percentage": (low_confidence / total_speeches)
                    * 100,
                    "very_low_confidence": very_low_confidence,
                    "very_low_confidence_percentage": (
                        very_low_confidence / total_speeches
                    )
                    * 100,
                },
            },
            "text_metrics": {
                "average_length": avg_text_length,
                "median_length": median_text_length,
                "min_length": min_text_length,
                "max_length": max_text_length,
                "truncated_count": truncated_count,
                "truncated_percentage": truncated_percentage,
                "length_by_method": text_length_by_method,
            },
        }

        # Add protocol stats if available
        if protocol_stats:
            report["protocol_metrics"] = protocol_stats

        return report

    def save_quality_report(self, report: Dict[str, Any], filename: str) -> Path:
        """
        Save a quality report to a JSON file.

        Args:
            report: Dictionary with quality metrics
            filename: Base filename for the report

        Returns:
            Path to the saved file
        """
        # Ensure filename has .json extension
        if not filename.endswith(".json"):
            filename = f"{filename}.json"

        # Create output path
        output_path = self.output_dir / filename

        # Create JSON encoder for datetime objects
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                return super().default(obj)

        # Write the report
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, cls=DateTimeEncoder, indent=2, ensure_ascii=False)

        logger.info(f"Saved data quality report to {output_path}")
        return output_path

    def generate_quality_visualizations(
        self, df_speeches: pd.DataFrame, base_filename: str, save_plots: bool = True
    ) -> Dict[str, Union[Figure, Path]]:
        """
        Generate visualizations of extraction quality metrics.

        Args:
            df_speeches: DataFrame containing speech data
            base_filename: Base filename for the plots
            save_plots: Whether to save plots to disk

        Returns:
            Dictionary of plot figures or file paths
        """
        if len(df_speeches) == 0:
            logger.warning("No speech data available for visualizations")
            return {}

        # Create a directory for figures
        figures_dir = self.output_dir / "figures"
        figures_dir.mkdir(exist_ok=True)

        # Dictionary to store figures or paths
        visualizations = {}

        # 1. Extraction Method Distribution (Pie chart)
        method_counts = df_speeches["extraction_method"].value_counts()
        fig1, ax1 = plt.subplots(figsize=(8, 6))
        ax1.pie(
            method_counts,
            labels=method_counts.index,
            autopct="%1.1f%%",
            startangle=90,
            shadow=True,
            explode=[0.1 if m == "xml" else 0 for m in method_counts.index],
        )
        ax1.axis("equal")
        ax1.set_title("Distribution of Extraction Methods")

        if save_plots:
            method_plot_path = figures_dir / f"{base_filename}_extraction_methods.png"
            fig1.savefig(method_plot_path)
            visualizations["method_distribution"] = method_plot_path
        else:
            visualizations["method_distribution"] = fig1

        # 2. Extraction Status Distribution (Pie chart)
        status_counts = df_speeches["extraction_status"].value_counts()
        fig2, ax2 = plt.subplots(figsize=(8, 6))
        ax2.pie(
            status_counts,
            labels=status_counts.index,
            autopct="%1.1f%%",
            startangle=90,
            shadow=True,
            explode=[0.1 if s == "complete" else 0 for s in status_counts.index],
        )
        ax2.axis("equal")
        ax2.set_title("Distribution of Extraction Status")

        if save_plots:
            status_plot_path = figures_dir / f"{base_filename}_extraction_status.png"
            fig2.savefig(status_plot_path)
            visualizations["status_distribution"] = status_plot_path
        else:
            visualizations["status_distribution"] = fig2

        # 3. Confidence Score Distribution (Histogram)
        fig3, ax3 = plt.subplots(figsize=(10, 6))
        ax3.hist(
            df_speeches["extraction_confidence"],
            bins=20,
            color="skyblue",
            edgecolor="black",
        )
        ax3.set_title("Distribution of Extraction Confidence Scores")
        ax3.set_xlabel("Confidence Score")
        ax3.set_ylabel("Number of Speeches")
        ax3.grid(True, linestyle="--", alpha=0.7)
        ax3.axvline(
            0.8, color="red", linestyle="--", label="High Confidence Threshold (0.8)"
        )
        ax3.axvline(
            0.5,
            color="orange",
            linestyle="--",
            label="Medium Confidence Threshold (0.5)",
        )
        ax3.axvline(
            0.2, color="green", linestyle="--", label="Low Confidence Threshold (0.2)"
        )
        ax3.legend()

        if save_plots:
            confidence_plot_path = (
                figures_dir / f"{base_filename}_confidence_distribution.png"
            )
            fig3.savefig(confidence_plot_path)
            visualizations["confidence_distribution"] = confidence_plot_path
        else:
            visualizations["confidence_distribution"] = fig3

        # 4. Text Length by Extraction Method (Box plot) - if text data available
        if "text" in df_speeches.columns:
            # Calculate text length
            df_speeches["text_length"] = df_speeches["text"].str.len()

            # Create a box plot of text length by extraction method
            fig4, ax4 = plt.subplots(figsize=(12, 8))

            # Get methods in order of confidence
            methods = ["xml", "pattern", "page", "none"]
            methods = [
                m for m in methods if m in df_speeches["extraction_method"].unique()
            ]

            # Create boxplot
            df_speeches.boxplot(
                column="text_length",
                by="extraction_method",
                ax=ax4,
                vert=True,
                patch_artist=True,
                order=methods,
            )

            ax4.set_title("Text Length by Extraction Method")
            ax4.set_xlabel("Extraction Method")
            ax4.set_ylabel("Text Length (characters)")
            ax4.grid(True, linestyle="--", alpha=0.7)

            # Add mean values as text annotations
            for i, method in enumerate(methods):
                method_data = df_speeches[df_speeches["extraction_method"] == method][
                    "text_length"
                ]
                if not method_data.empty:
                    mean_val = method_data.mean()
                    ax4.text(
                        i + 1,
                        mean_val,
                        f"Mean: {int(mean_val)}",
                        horizontalalignment="center",
                        size="small",
                        color="black",
                        weight="semibold",
                    )

            if save_plots:
                length_plot_path = (
                    figures_dir / f"{base_filename}_text_length_by_method.png"
                )
                fig4.savefig(length_plot_path)
                visualizations["text_length_by_method"] = length_plot_path
            else:
                visualizations["text_length_by_method"] = fig4

        # 5. Combined visualization as a dashboard
        fig5 = plt.figure(figsize=(18, 12))

        # Distribution of extraction methods
        ax1 = fig5.add_subplot(221)
        ax1.pie(
            method_counts, labels=method_counts.index, autopct="%1.1f%%", startangle=90
        )
        ax1.axis("equal")
        ax1.set_title("Extraction Methods")

        # Distribution of extraction status
        ax2 = fig5.add_subplot(222)
        ax2.pie(
            status_counts, labels=status_counts.index, autopct="%1.1f%%", startangle=90
        )
        ax2.axis("equal")
        ax2.set_title("Extraction Status")

        # Confidence distribution
        ax3 = fig5.add_subplot(223)
        ax3.hist(
            df_speeches["extraction_confidence"],
            bins=20,
            color="skyblue",
            edgecolor="black",
        )
        ax3.set_title("Confidence Scores")
        ax3.set_xlabel("Confidence Score")
        ax3.set_ylabel("Number of Speeches")
        ax3.grid(True, linestyle="--", alpha=0.7)

        # Text summary or stats
        ax4 = fig5.add_subplot(224)
        ax4.axis("off")

        # Create a summary table
        total = len(df_speeches)
        xml_count = method_counts.get("xml", 0)
        complete_count = status_counts.get("complete", 0)
        high_conf_count = (df_speeches["extraction_confidence"] >= 0.8).sum()

        summary = [
            f"Total Speeches: {total}",
            (
                f"XML Extracted: {xml_count} ({xml_count/total*100:.1f}%)"
                if total > 0
                else "XML Extracted: 0 (0.0%)"
            ),
            (
                f"Complete Status: {complete_count} ({complete_count/total*100:.1f}%)"
                if total > 0
                else "Complete Status: 0 (0.0%)"
            ),
            (
                f"High Confidence: {high_conf_count} ({high_conf_count/total*100:.1f}%)"
                if total > 0
                else "High Confidence: 0 (0.0%)"
            ),
        ]

        if "text" in df_speeches.columns:
            avg_length = int(df_speeches["text_length"].mean())
            summary.append(f"Avg Text Length: {avg_length} chars")

        for i, line in enumerate(summary):
            ax4.text(0.1, 0.9 - i * 0.1, line, fontsize=12)

        ax4.set_title("Summary Statistics")

        fig5.tight_layout()

        if save_plots:
            dashboard_path = figures_dir / f"{base_filename}_quality_dashboard.png"
            fig5.savefig(dashboard_path)
            visualizations["dashboard"] = dashboard_path
        else:
            visualizations["dashboard"] = fig5

        logger.info(f"Generated {len(visualizations)} data quality visualizations")
        return visualizations

    def create_html_report(
        self, report: Dict[str, Any], visualizations: Dict[str, Path], filename: str
    ) -> Path:
        """
        Create an HTML report combining quality metrics and visualizations.

        Args:
            report: Dictionary with quality metrics
            visualizations: Dictionary of visualization file paths
            filename: Base filename for the HTML report

        Returns:
            Path to the HTML report
        """
        # Ensure filename has .html extension
        if not filename.endswith(".html"):
            filename = f"{filename}.html"

        # Create output path
        output_path = self.output_dir / filename

        # Create relative paths for visualizations
        visual_paths = {}
        for key, path in visualizations.items():
            if isinstance(path, Path):
                visual_paths[key] = path.relative_to(self.output_dir)
            else:
                # Skip non-path entries (might be Figure objects)
                continue

        # Format the generated time
        gen_time = report.get("generated_at", datetime.now())
        if isinstance(gen_time, str):
            formatted_time = gen_time
        else:
            formatted_time = gen_time.strftime("%Y-%m-%d %H:%M:%S")

        # Create HTML content
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bundestag Protocol Extraction Quality Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .dashboard {{
            margin: 20px 0;
            text-align: center;
        }}
        .dashboard img {{
            max-width: 100%;
            height: auto;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background-color: #f9f9f9;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 0 5px rgba(0,0,0,0.1);
        }}
        .metric-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #2980b9;
        }}
        .charts {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .chart {{
            text-align: center;
        }}
        .chart img {{
            max-width: 100%;
            height: auto;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #2980b9;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 0.9em;
            color: #7f8c8d;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Bundestag Protocol Extraction Quality Report</h1>
        <p>Generated on {formatted_time}</p>
        
        <!-- Main Dashboard -->
        <div class="dashboard">
            <h2>Quality Dashboard</h2>
            {f'<img src="{visual_paths.get("dashboard")}" alt="Quality Dashboard">' if "dashboard" in visual_paths else ''}
        </div>
        
        <!-- Key Metrics -->
        <h2>Key Metrics</h2>
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-title">Total Data</div>
                <p>Total Speeches: {report.get("total_speeches", 0)}</p>
                {'<p>Total Protocols: ' + str(report.get("protocol_metrics", {}).get("total_protocols", "N/A")) + '</p>' if "protocol_metrics" in report else ''}
                {'<p>Protocols with Speeches: ' + str(report.get("protocol_metrics", {}).get("protocols_with_speeches", "N/A")) + '</p>' if "protocol_metrics" in report else ''}
                {'<p>Avg Speeches per Protocol: ' + str(round(report.get("protocol_metrics", {}).get("avg_speeches_per_protocol", 0), 1)) + '</p>' if "protocol_metrics" in report else ''}
            </div>
            
            <div class="metric-card">
                <div class="metric-title">Extraction Methods</div>
                <p>XML: {report.get("extraction_methods", {}).get("counts", {}).get("xml", 0)} 
                   ({report.get("extraction_methods", {}).get("percentages", {}).get("xml", 0):.1f}%)</p>
                <p>Pattern: {report.get("extraction_methods", {}).get("counts", {}).get("pattern", 0)}
                   ({report.get("extraction_methods", {}).get("percentages", {}).get("pattern", 0):.1f}%)</p>
                <p>Page: {report.get("extraction_methods", {}).get("counts", {}).get("page", 0)}
                   ({report.get("extraction_methods", {}).get("percentages", {}).get("page", 0):.1f}%)</p>
                <p>None: {report.get("extraction_methods", {}).get("counts", {}).get("none", 0)}
                   ({report.get("extraction_methods", {}).get("percentages", {}).get("none", 0):.1f}%)</p>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">Extraction Status</div>
                <p>Complete: {report.get("extraction_status", {}).get("counts", {}).get("complete", 0)}
                   ({report.get("extraction_status", {}).get("percentages", {}).get("complete", 0):.1f}%)</p>
                <p>Partial: {report.get("extraction_status", {}).get("counts", {}).get("partial", 0)}
                   ({report.get("extraction_status", {}).get("percentages", {}).get("partial", 0):.1f}%)</p>
                <p>Failed: {report.get("extraction_status", {}).get("counts", {}).get("failed", 0)}
                   ({report.get("extraction_status", {}).get("percentages", {}).get("failed", 0):.1f}%)</p>
                <p>Pending: {report.get("extraction_status", {}).get("counts", {}).get("pending", 0)}
                   ({report.get("extraction_status", {}).get("percentages", {}).get("pending", 0):.1f}%)</p>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">Confidence Metrics</div>
                <p>Average Confidence: {report.get("confidence_metrics", {}).get("average", 0):.2f}</p>
                <p>Median Confidence: {report.get("confidence_metrics", {}).get("median", 0):.2f}</p>
                <p>High Confidence (≥0.8): {report.get("confidence_metrics", {}).get("distribution", {}).get("high_confidence", 0)}
                   ({report.get("confidence_metrics", {}).get("distribution", {}).get("high_confidence_percentage", 0):.1f}%)</p>
                <p>Medium Confidence (0.5-0.8): {report.get("confidence_metrics", {}).get("distribution", {}).get("medium_confidence", 0)}
                   ({report.get("confidence_metrics", {}).get("distribution", {}).get("medium_confidence_percentage", 0):.1f}%)</p>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">Text Quality</div>
                <p>Average Length: {int(report.get("text_metrics", {}).get("average_length", 0))} characters</p>
                <p>Median Length: {int(report.get("text_metrics", {}).get("median_length", 0))} characters</p>
                <p>Truncated Text: {report.get("text_metrics", {}).get("truncated_count", 0)}
                   ({report.get("text_metrics", {}).get("truncated_percentage", 0):.1f}%)</p>
            </div>
        </div>
        
        <!-- Visualizations -->
        <h2>Detailed Visualizations</h2>
        <div class="charts">
            <div class="chart">
                <h3>Extraction Methods</h3>
                {f'<img src="{visual_paths.get("method_distribution")}" alt="Extraction Methods">' if "method_distribution" in visual_paths else ''}
            </div>
            
            <div class="chart">
                <h3>Extraction Status</h3>
                {f'<img src="{visual_paths.get("status_distribution")}" alt="Extraction Status">' if "status_distribution" in visual_paths else ''}
            </div>
            
            <div class="chart">
                <h3>Confidence Distribution</h3>
                {f'<img src="{visual_paths.get("confidence_distribution")}" alt="Confidence Distribution">' if "confidence_distribution" in visual_paths else ''}
            </div>
            
            <div class="chart">
                <h3>Text Length by Method</h3>
                {f'<img src="{visual_paths.get("text_length_by_method")}" alt="Text Length by Method">' if "text_length_by_method" in visual_paths else ''}
            </div>
        </div>
        
        <!-- Text Length by Method -->
        <h2>Text Length by Extraction Method</h2>
        <table>
            <tr>
                <th>Extraction Method</th>
                <th>Average Length</th>
                <th>Median Length</th>
                <th>Min Length</th>
                <th>Max Length</th>
            </tr>
"""

        # Add rows for each extraction method
        for method, metrics in (
            report.get("text_metrics", {}).get("length_by_method", {}).items()
        ):
            html_content += f"""
            <tr>
                <td>{method}</td>
                <td>{int(metrics.get("average", 0))}</td>
                <td>{int(metrics.get("median", 0))}</td>
                <td>{metrics.get("min", 0)}</td>
                <td>{metrics.get("max", 0)}</td>
            </tr>"""

        html_content += """
        </table>
        
        <!-- Research Recommendations -->
        <h2>Recommendations for Researchers</h2>
        <div class="metric-card">
            <p>When using this data for research purposes, consider the following guidelines:</p>
            <ul>
                <li><strong>For high precision analysis:</strong> Filter speeches with <code>extraction_method == "xml"</code> and <code>extraction_status == "complete"</code></li>
                <li><strong>For balanced coverage:</strong> Filter speeches with <code>extraction_confidence >= 0.5</code></li>
                <li><strong>For maximum recall:</strong> Include all speeches but apply weighting based on confidence scores</li>
                <li><strong>In pandas:</strong> Use the provided helper columns: <code>is_xml_extracted</code>, <code>is_complete</code>, and <code>is_high_confidence</code></li>
            </ul>
            
            <p>Example pandas code:</p>
            <pre>
import pandas as pd

# Load the speeches data
df = pd.read_csv("bundestag_speeches.csv")

# For high precision analysis
high_quality = df[df['is_xml_extracted'] & df['is_complete']]

# For balanced coverage
balanced = df[df['extraction_confidence'] >= 0.5]

# For maximum recall with weighting
df['analysis_weight'] = df['extraction_confidence'].clip(0.1, 1.0)
            </pre>
        </div>
        
        <div class="footer">
            <p>Generated by Bundestag Protocol Extractor</p>
        </div>
    </div>
</body>
</html>
"""

        # Write HTML file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Created HTML quality report at {output_path}")
        return output_path
