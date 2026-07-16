"""
Regression tests for report generator appendix behavior.
"""

import sys
import unittest
import io
import zipfile
from unittest.mock import patch

from matplotlib.figure import Figure

sys.path.insert(0, 'Program')

from data_loader import GrainSizeData
from k_calculations import CalculationStatus, KCalculationResult
from report_generator import ReportGenerator
from unit_conversions import HydraulicConductivityUnit


def build_dataset(name: str = 'Sample A') -> GrainSizeData:
    return GrainSizeData(
        sample_name=name,
        temperature=20.0,
        porosity=0.35,
        particle_sizes=[4.75, 2.0, 1.0, 0.5, 0.25, 0.125, 0.063],
        percent_passing=[100.0, 95.0, 82.0, 61.0, 38.0, 14.0, 4.0],
    )


def build_results() -> list[KCalculationResult]:
    return [
        KCalculationResult(
            method_name='Hazen',
            k_value=1.0e-4,
            formula_used='k = c * d10^2',
            status=CalculationStatus.OK,
            status_message='',
            conditions_met=True,
            temperature=20.0,
            porosity=0.35,
            grain_size_used='D10',
        ),
    ]


class TestReportGeneratorAppendices(unittest.TestCase):
    def setUp(self):
        self.generator = ReportGenerator()
        self.dataset = build_dataset()
        self.results = build_results()

    def test_k_value_bar_chart_uses_canonical_m_s_unit(self):
        ms_uri = self.generator._create_k_value_bar_chart(
            self.results, {'display_unit': HydraulicConductivityUnit.M_PER_S}
        )
        md_context_uri = self.generator._create_k_value_bar_chart(
            self.results, {'display_unit': HydraulicConductivityUnit.M_PER_DAY}
        )

        self.assertTrue(ms_uri.startswith('data:image/png;base64,'))
        self.assertEqual(ms_uri, md_context_uri)

    def test_individual_report_includes_k_bar_when_selected(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={'plots': True},
            k_results=self.results,
            selected_plots={'grain_size_curve', 'k_value_bar'},
        )
        self.assertIn('Grain Size Distribution Curve', html)
        self.assertIn('Hydraulic Conductivity by Method', html)

    def test_individual_report_omits_k_bar_when_not_selected(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={'plots': True},
            k_results=self.results,
            selected_plots={'grain_size_curve'},
        )
        self.assertIn('Grain Size Distribution Curve', html)
        self.assertNotIn('Hydraulic Conductivity by Method', html)

    def test_comparison_report_can_omit_reliability_matrix(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35},
        ]
        html = self.generator.generate_comparison_report(
            [self.dataset, sample_b],
            sections={'plots': True},
            sample_details=details,
            selected_plots={'distribution_overlay', 'statistical_boxplots'},
        )
        self.assertIn('Grain Size Distribution Comparison', html)
        self.assertNotIn('Reliability Matrix', html)

    def test_report_class_fractions_switch_to_heatmap_for_large_scopes(self):
        cases = ((1, 'bars'), (7, 'bars'), (15, 'heatmap'), (51, 'heatmap'))
        for count, expected_layout in cases:
            details = [
                {'dataset': build_dataset(f'Sample {index + 1}'), 'k_results': []}
                for index in range(count)
            ]
            with self.subTest(count=count), patch(
                'plot_export.export_comparison_spec',
                return_value='data:image/png;base64,test',
            ) as renderer:
                self.generator._create_comparison_grain_size_histogram(details, None)

            spec = renderer.call_args.args[0]
            figsize = renderer.call_args.kwargs['figsize']
            self.assertEqual(spec.histogram_layout, expected_layout)
            self.assertEqual(spec.show_legend, expected_layout == 'bars')
            self.assertEqual(spec.dense_report_layout, count >= 12)
            self.assertEqual(figsize, (13, 7.4) if count >= 12 else (12, 7.0))

    def test_large_grouped_scope_keeps_bars_when_only_four_groups_are_plotted(self):
        details = []
        for index in range(51):
            dataset = build_dataset(f'Sample {index + 1}')
            group_name = f'Layer {(index % 4) + 1}'
            dataset.group_name = group_name
            details.append({
                'dataset': dataset,
                'group_name': group_name,
                'k_results': [],
            })

        with patch(
            'plot_export.export_comparison_spec',
            return_value='data:image/png;base64,test',
        ) as renderer:
            self.generator._create_comparison_grain_size_histogram(
                details,
                None,
                breakdown='group',
            )

        spec = renderer.call_args.args[0]
        self.assertEqual(spec.histogram_layout, 'bars')
        self.assertTrue(spec.show_legend)
        self.assertTrue(spec.dense_report_layout)
        self.assertEqual(renderer.call_args.kwargs['figsize'], (13, 7.4))

    def test_large_report_explains_the_automatic_class_fraction_heatmap(self):
        details = [
            {
                'label': f'Sample {index + 1}',
                'dataset': build_dataset(f'Sample {index + 1}'),
                'k_results': [],
            }
            for index in range(15)
        ]
        sections = {
            'cover_page': False,
            'executive_summary': False,
            'methodology': False,
            'results': False,
            'plots': True,
            'interpretation': False,
            'grain_comparison': False,
            'k_statistics': False,
        }

        with patch(
            'plot_export.export_comparison_spec',
            return_value='data:image/png;base64,test',
        ):
            html = self.generator.generate_comparison_report(
                [item['dataset'] for item in details],
                sections=sections,
                sample_details=details,
                selected_plots={'grain_size_histogram_comparison'},
                plot_breakdowns={'grain_size_histogram_comparison': 'dataset'},
            )

        self.assertIn('Large-batch layout:', html)
        self.assertIn('Heatmap shown for 15 samples', html)
        self.assertIn('color shows weight percent (0-100)', html)

    def test_large_report_class_fraction_heatmap_has_one_row_per_sample(self):
        details = [
            {'dataset': build_dataset(f'Sample {index + 1}'), 'k_results': []}
            for index in range(15)
        ]
        with patch(
            'gui.report_plot_style.get_report_style_overrides',
            return_value={},
        ):
            spec = self.generator._build_comparison_spec(
                details,
                None,
                plot_type='histogram',
                display_mode='overlay',
                breakdown='dataset',
            )
        spec.histogram_layout = 'heatmap'
        spec.show_legend = False

        from gui.comparison_plot_spec import render_comparison

        figure = Figure(figsize=(12, 7))
        try:
            render_comparison(figure, spec)
            heatmap_ax = figure.axes[0]
            self.assertEqual(len(figure.axes), 2)  # heatmap + quantitative colorbar
            self.assertEqual(len(heatmap_ax.images), 1)
            self.assertEqual(heatmap_ax.images[0].get_array().shape[0], 15)
            self.assertIsNone(heatmap_ax.get_legend())
            self.assertIn('heatmap, n=15', heatmap_ax.get_title())
            self.assertEqual(
                {label.get_fontsize() for label in heatmap_ax.get_yticklabels()},
                {float(spec.style.tick_fontsize)},
            )
            self.assertEqual(
                {label.get_rotation() for label in heatmap_ax.get_xticklabels()},
                {30.0},
            )
        finally:
            figure.clear()

    def test_large_report_uses_landscape_plot_pages_and_dense_legend(self):
        details = [
            {
                'label': f'Sample {index + 1}',
                'dataset': build_dataset(f'Sample {index + 1}'),
                'k_results': [],
            }
            for index in range(25)
        ]
        sections = {
            'cover_page': False,
            'executive_summary': False,
            'methodology': False,
            'results': False,
            'plots': True,
            'interpretation': False,
            'grain_comparison': False,
            'k_statistics': False,
        }
        captured = []

        def fake_spec(spec, **kwargs):
            captured.append((spec, kwargs))
            return 'data:image/png;base64,test'

        from gui.plot_styles import PRESENTATION_STYLE

        with patch(
            'gui.report_plot_style.get_report_style_overrides',
            return_value={},
        ), patch('plot_export.export_comparison_spec', side_effect=fake_spec):
            html = self.generator.generate_comparison_report(
                [item['dataset'] for item in details],
                sections=sections,
                sample_details=details,
                selected_plots={'distribution_overlay'},
                plot_breakdowns={'distribution_overlay': 'dataset'},
                plot_style=PRESENTATION_STYLE,
            )

        spec, kwargs = captured[0]
        self.assertTrue(spec.dense_report_layout)
        self.assertEqual(kwargs['figsize'], (13, 7.4))
        self.assertEqual(spec.style.title_fontsize, PRESENTATION_STYLE.title_fontsize)
        self.assertEqual(spec.style.label_fontsize, PRESENTATION_STYLE.label_fontsize)
        self.assertEqual(spec.style.tick_fontsize, PRESENTATION_STYLE.tick_fontsize)
        self.assertEqual(spec.style.legend_fontsize, PRESENTATION_STYLE.legend_fontsize)
        self.assertEqual(spec.style.curve_linewidth, PRESENTATION_STYLE.curve_linewidth)
        self.assertEqual(spec.style.legend_loc, 'upper center')
        self.assertEqual(spec.style.legend_bbox_to_anchor, (0.5, -0.18))
        self.assertEqual(spec.style.legend_ncol, 0)
        self.assertTrue(spec.automatic_report_legend_layout)
        self.assertIn('class="comparison-plot-page landscape-plot-page"', html)

    def test_large_report_preserves_explicit_customize_values(self):
        import dataclasses
        from gui.plot_styles import PRESENTATION_STYLE

        details = [
            {'dataset': build_dataset(f'Sample {index + 1}'), 'k_results': []}
            for index in range(25)
        ]
        custom = dataclasses.replace(
            PRESENTATION_STYLE,
            title_fontsize=23,
            label_fontsize=17,
            tick_fontsize=13,
            legend_fontsize=12,
            legend_loc='lower center',
            legend_bbox_to_anchor=(0.5, 1.12),
            legend_ncol=2,
            curve_linewidth=3.25,
            curve_markers_visible=False,
            curve_markersize=6.5,
            grid_show=False,
            show_minor_grid=False,
            grid_alpha=0.35,
            minor_grid_alpha=0.1,
            grid_linestyle=':',
        )
        overrides = {
            'title_fontsize': 23,
            'label_fontsize': 17,
            'tick_fontsize': 13,
            'legend_fontsize': 12,
            'legend_loc': 'lower center',
            'legend_bbox_to_anchor': (0.5, 1.12),
            'legend_ncol': 2,
            'curve_linewidth': 3.25,
            'curve_markers_visible': False,
            'curve_markersize': 6.5,
            'grid_show': False,
            'show_minor_grid': False,
            'grid_alpha': 0.35,
            'minor_grid_alpha': 0.1,
            'grid_linestyle': ':',
        }

        with patch(
            'gui.report_plot_style.get_report_style_overrides',
            return_value=overrides,
        ):
            spec = self.generator._build_comparison_spec(
                details,
                None,
                plot_type='distribution',
                breakdown='dataset',
                plot_style=custom,
            )

        self.assertEqual(spec.style, custom)
        self.assertFalse(spec.automatic_report_legend_layout)

    def test_dense_report_legend_stays_below_the_x_axis_title(self):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from gui.comparison_plot_spec import render_comparison
        from plot_export import _apply_comparison_spec_layout

        details = []
        for index in range(25):
            dataset = build_dataset(f'Sample {index + 1}')
            dataset.group_name = f'Group {(index // 7) + 1}'
            details.append({
                'dataset': dataset,
                'group_name': dataset.group_name,
                'k_results': [],
            })
        with patch(
            'gui.report_plot_style.get_report_style_overrides',
            return_value={},
        ):
            spec = self.generator._build_comparison_spec(
                details,
                None,
                plot_type='distribution',
                breakdown='dataset',
            )
        figure = Figure(figsize=(13, 7.4))
        FigureCanvasAgg(figure)
        try:
            render_comparison(figure, spec)
            _apply_comparison_spec_layout(figure, spec)
            figure.canvas.draw()
            axes = figure.axes[0]
            renderer = figure.canvas.get_renderer()
            legend_bounds = axes.get_legend().get_window_extent(renderer)
            label_bounds = axes.xaxis.label.get_window_extent(renderer)
            self.assertLess(legend_bounds.y1, label_bounds.y0)
        finally:
            figure.clear()

    def test_small_report_keeps_portrait_plot_page_and_original_style(self):
        details = [
            {'dataset': build_dataset(f'Sample {index + 1}'), 'k_results': []}
            for index in range(7)
        ]
        with patch(
            'plot_export.export_comparison_spec',
            return_value='data:image/png;base64,test',
        ) as renderer:
            html = self.generator.generate_comparison_report(
                [item['dataset'] for item in details],
                sections={'plots': True, 'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'distribution_overlay'},
            )

        spec = renderer.call_args.args[0]
        self.assertFalse(spec.dense_report_layout)
        self.assertIn('class="comparison-plot-page"', html)
        self.assertNotIn('class="comparison-plot-page landscape-plot-page"', html)

    def test_comparison_report_renders_plots_via_shared_spec(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'group_name': 'Layer A', 'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'group_name': 'Layer B', 'temperature': 20.0, 'porosity': 0.35},
        ]
        captured = []

        def fake_spec(spec, **kwargs):
            captured.append(spec)
            return 'data:image/png;base64,spec'

        with patch('plot_export.export_comparison_spec', side_effect=fake_spec):
            html = self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={'plots': True, 'k_statistics': False,
                          'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'distribution_overlay', 'k_value_comparison'},
            )

        by_type = {spec.current_plot_type: spec for spec in captured}
        # Both comparison plots route through the shared render_comparison spec.
        self.assertIn('distribution', by_type)
        self.assertIn('k-values', by_type)
        # Named groups -> group-aware breakdown, matching the Comparison tab.
        self.assertTrue(by_type['distribution'].use_group_breakdown)
        # K bars use m/s, consistent with the report's K tables/boxplot.
        self.assertEqual(
            by_type['k-values'].display_unit, HydraulicConductivityUnit.M_PER_S
        )
        self.assertIn('Grain Size Distribution Comparison', html)
        self.assertIn('Hydraulic Conductivity by Method', html)

    def test_comparison_report_honors_per_plot_breakdown(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'group_name': 'Layer A', 'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'group_name': 'Layer B', 'temperature': 20.0, 'porosity': 0.35},
        ]
        captured = []

        def fake_spec(spec, **kwargs):
            captured.append(spec)
            return 'data:image/png;base64,spec'

        with patch('plot_export.export_comparison_spec', side_effect=fake_spec):
            self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={'plots': True, 'k_statistics': False,
                          'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'distribution_overlay', 'k_value_comparison'},
                plot_breakdowns={'distribution_overlay': 'dataset',
                                 'k_value_comparison': 'group'},
            )

        by_type = {spec.current_plot_type: spec for spec in captured}
        # Forced per-dataset distribution flattens the breakdown even though the
        # samples carry named groups; the K bars stay grouped.
        self.assertFalse(by_type['distribution'].use_group_breakdown)
        self.assertTrue(by_type['k-values'].use_group_breakdown)

    def test_comparison_report_can_omit_k_value_bar(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35},
        ]
        html = self.generator.generate_comparison_report(
            [self.dataset, sample_b],
            sections={'plots': True},
            sample_details=details,
            selected_plots={'distribution_overlay'},
        )
        self.assertIn('Grain Size Distribution Comparison', html)
        self.assertNotIn('Hydraulic Conductivity by Method', html)

    def test_comparison_report_includes_k_distribution_when_selected(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'group_name': 'Layer A', 'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'group_name': 'Layer B', 'temperature': 20.0, 'porosity': 0.35},
        ]
        captured = []

        def fake_spec(spec, **kwargs):
            captured.append(spec)
            return 'data:image/png;base64,spec'

        with patch('plot_export.export_comparison_spec', side_effect=fake_spec):
            html = self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={'plots': True, 'k_statistics': False,
                          'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'k_distribution'},
            )

        kdist = [s for s in captured if s.current_plot_type == 'k-distribution']
        # The K-distribution renders through the shared spec as a lognormal
        # histogram (the new default view), not the empirical CDF.
        self.assertEqual(len(kdist), 1)
        self.assertEqual(kdist[0].k_dist_view, 'histogram')
        self.assertIn('Lognormal', html)

    def test_comparison_report_both_breakdown_emits_two_images(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'group_name': 'Layer A', 'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'group_name': 'Layer B', 'temperature': 20.0, 'porosity': 0.35},
        ]
        captured = []

        def fake_spec(spec, **kwargs):
            captured.append(spec)
            return 'data:image/png;base64,spec'

        with patch('plot_export.export_comparison_spec', side_effect=fake_spec):
            html = self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={'plots': True, 'k_statistics': False,
                          'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'k_distribution'},
                plot_breakdowns={'k_distribution': 'both'},
            )

        kdist = [s for s in captured if s.current_plot_type == 'k-distribution']
        # "Both" renders the per-group and per-dataset variants as two figures.
        self.assertEqual(len(kdist), 2)
        self.assertEqual({s.use_group_breakdown for s in kdist}, {True, False})
        self.assertEqual(html.count('alt="K Distribution"'), 2)
        self.assertIn('per group', html)
        self.assertIn('per dataset', html)

    def _grouped_details(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'group_name': 'Layer A', 'temperature': 20.0, 'porosity': 0.35},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'group_name': 'Layer B', 'temperature': 20.0, 'porosity': 0.35},
        ]
        return [self.dataset, sample_b], details

    def _capture_distribution_spec(self, palette_name):
        from unittest.mock import patch
        import gui.report_plot_style as rps
        from gui.group_styles import set_group_color, clear_group_color

        datasets, details = self._grouped_details()
        captured = []

        def fake_spec(spec, **kwargs):
            captured.append(spec)
            return 'data:image/png;base64,spec'

        try:
            set_group_color('Layer A', '#ff0000')  # persisted Comparison-tab override
            rps.set_report_palette(palette_name)
            with patch('plot_export.export_comparison_spec', side_effect=fake_spec):
                self.generator.generate_comparison_report(
                    datasets,
                    sections={'plots': True, 'k_statistics': False,
                              'results': False, 'interpretation': False},
                    sample_details=details,
                    selected_plots={'distribution_overlay'},
                )
        finally:
            clear_group_color('Layer A')
            rps.set_report_palette('Categorical')
            rps._reset_cache_for_tests()
        return [s for s in captured if s.current_plot_type == 'distribution'][0]

    def test_non_categorical_palette_overrides_group_colors(self):
        spec = self._capture_distribution_spec('Viridis')
        colors = [c.lower() for c in spec.effective_colors]
        # The persisted red Layer-A override is ignored: a non-Categorical palette
        # is authoritative and re-colours every group.
        self.assertNotIn('#ff0000', colors)

    def test_categorical_palette_keeps_group_color_override(self):
        spec = self._capture_distribution_spec('Categorical')
        colors = [c.lower() for c in spec.effective_colors]
        # Categorical keeps the user's Comparison-tab group colour.
        self.assertIn('#ff0000', colors)

    def test_group_colors_spread_across_colormap_with_many_datasets(self):
        # Regression: with many datasets in a few groups, the groups must sample
        # the colormap by GROUP count (spread across the whole map), not land in
        # the first slice. palette_name drives the per-group re-sampling.
        from gui.comparison_plot_capture import build_comparison_spec
        from gui.plot_constants import palette_colors

        datasets = []
        groups = {}
        for g in range(3):
            for k in range(4):  # 4 datasets per group -> 12 datasets, 3 groups
                d = build_dataset(f'S{g}-{k}')
                datasets.append(d)
                groups[d.sample_name] = f'Layer {g}'

        spec = build_comparison_spec(
            datasets,
            dataset_groups=groups,
            palette=palette_colors('Viridis', len(datasets)),
            palette_name='Viridis',
            group_palette_authoritative=True,
        )
        group_colors = list(spec.group_color_map.values())
        # Three groups -> the proper 3-colour spread, not the first 3 of a
        # 12-colour sample (which would all be dark purple/blue).
        self.assertEqual(group_colors, palette_colors('Viridis', 3))
        self.assertEqual(len(set(group_colors)), 3)

    def test_k_scope_boxplot_receives_global_plot_style(self):
        from unittest.mock import patch
        import dataclasses
        from gui.plot_styles import PROFESSIONAL_STYLE

        datasets, details = self._grouped_details()
        sentinel = dataclasses.replace(PROFESSIONAL_STYLE, title_fontsize=29)
        captured = {}

        def fake_boxplot(series, **kwargs):
            captured.update(kwargs)
            return 'data:image/png;base64,box'

        with patch('plot_export.export_k_scope_boxplot', side_effect=fake_boxplot):
            self.generator.generate_comparison_report(
                datasets,
                sections={'plots': True, 'k_statistics': False,
                          'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'statistical_boxplots'},
                plot_style=sentinel,
            )
        # The K box-plot now receives the global style (was previously unstyled).
        self.assertIn('style', captured)
        self.assertEqual(captured['style'].title_fontsize, 29)

    def test_comparison_report_includes_per_sample_plots_when_selected(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35, 'plot_context': None},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35, 'plot_context': None},
        ]
        html = self.generator.generate_comparison_report(
            [self.dataset, sample_b],
            sections={'plots': True, 'k_statistics': False,
                      'results': False, 'interpretation': False},
            sample_details=details,
            selected_plots={'per_sample_grain', 'per_sample_kbar'},
        )
        # One per-sample sub-section per sample, with both plot types.
        self.assertIn('Individual Sample Plots', html)
        self.assertIn('<h3>Sample A</h3>', html)
        self.assertIn('<h3>Sample B</h3>', html)
        self.assertIn('Sample A grain size distribution', html)
        self.assertIn('Sample A K-value bar chart', html)

    def test_k_bar_colors_follow_palette_not_preset(self):
        # K-bar colours come from the palette, never the preset: a colormap
        # samples one colour per method; Categorical keeps semantic method colours.
        import gui.report_plot_style as rps
        from gui.plot_constants import METHOD_COLORS, palette_colors

        methods = ['Hazen', 'Beyer', 'Terzaghi']
        try:
            rps.set_report_palette('Categorical')
            self.assertEqual(
                self.generator._k_bar_method_colors(methods),
                [METHOD_COLORS[m] for m in methods],
            )

            rps.set_report_palette('Viridis')
            rps.set_report_style_preset('Presentation')
            with_pres = self.generator._k_bar_method_colors(methods)
            rps.set_report_style_preset('Classic')
            with_classic = self.generator._k_bar_method_colors(methods)
            self.assertEqual(with_pres, palette_colors('Viridis', 3))
            # The preset must not influence the K-bar colours.
            self.assertEqual(with_pres, with_classic)
        finally:
            rps.set_report_palette('Categorical')
            rps.set_report_style_preset('Professional')
            rps._reset_cache_for_tests()

    def test_individual_report_grain_curve_follows_palette(self):
        # One rule everywhere: a chosen colormap palette colours the single grain
        # curve too (Categorical keeps the preset colour). Fonts stay from the preset.
        import gui.report_plot_style as rps

        seen = []
        original = self.generator._create_grain_size_plot

        def spy(dataset, plot_context=None, curve_color=None):
            resolved = curve_color if curve_color is not None else self.generator._palette_curve_color()
            seen.append(resolved)
            return original(dataset, plot_context, curve_color)

        self.generator._create_grain_size_plot = spy
        try:
            rps.set_report_palette('Categorical')
            self.generator.generate_grain_size_report(
                self.dataset, sections={'plots': True}, selected_plots={'grain_size_curve'})
            rps.set_report_palette('Viridis')
            self.generator.generate_grain_size_report(
                self.dataset, sections={'plots': True}, selected_plots={'grain_size_curve'})
        finally:
            rps.set_report_palette('Categorical')
            rps._reset_cache_for_tests()

        self.assertEqual(len(seen), 2)
        self.assertIsNone(seen[0])                       # Categorical → preset colour
        self.assertTrue(seen[1] and seen[1].startswith('#'))  # Viridis → palette colour

    def test_per_sample_grain_curves_use_palette_colors(self):
        # Each per-sample grain curve takes that sample's overlay (palette) colour
        # while keeping the global typography — so Presentation fonts + palette
        # colours can be combined on the individual plots.
        import gui.report_plot_style as rps

        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35, 'plot_context': None},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35, 'plot_context': None},
        ]
        seen = []
        original = self.generator._create_grain_size_plot

        def spy(dataset, plot_context=None, curve_color=None):
            seen.append((dataset.sample_name, curve_color))
            return original(dataset, plot_context, curve_color)

        self.generator._create_grain_size_plot = spy
        try:
            rps.set_report_palette('Viridis')
            self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={'plots': True, 'k_statistics': False,
                          'results': False, 'interpretation': False},
                sample_details=details,
                selected_plots={'per_sample_grain'},
            )
        finally:
            rps.set_report_palette('Categorical')
            rps._reset_cache_for_tests()

        colors = [c for _name, c in seen]
        self.assertEqual(len(colors), 2)
        self.assertTrue(all(c and c.startswith('#') for c in colors))
        self.assertNotEqual(colors[0], colors[1])  # distinct per-sample palette colours

    def test_comparison_report_omits_per_sample_plots_by_default(self):
        sample_b = build_dataset('Sample B')
        details = [
            {'label': 'Sample A', 'dataset': self.dataset, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35, 'plot_context': None},
            {'label': 'Sample B', 'dataset': sample_b, 'k_results': self.results,
             'temperature': 20.0, 'porosity': 0.35, 'plot_context': None},
        ]
        html = self.generator.generate_comparison_report(
            [self.dataset, sample_b],
            sections={'plots': True, 'k_statistics': False,
                      'results': False, 'interpretation': False},
            sample_details=details,
            selected_plots={'distribution_overlay'},
        )
        self.assertNotIn('Individual Sample Plots', html)

    def test_percentile_appendix_uses_curve_interpolation(self):
        html = self.generator._create_percentiles_table(self.dataset)

        self.assertIn('>0.069<', html)
        self.assertIn('>0.100<', html)
        self.assertIn('>0.380<', html)
        self.assertIn('>2.000<', html)

    def test_single_visible_appendix_is_labeled_appendix_a(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
        )

        self.assertIn('Appendix A: Raw Measurement Data', html)
        self.assertNotIn('Appendix C: Raw Measurement Data', html)

    def test_alpha_numeric_appendix_labels_are_supported_in_live_report_output(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': True,
                'gradation': False,
                'data_quality': False,
            },
            appendix_label_config={
                'scheme': 'alpha_numeric',
                'alpha_numeric_root': 'A',
            },
        )

        self.assertIn('A1: Detailed Percentile Data', html)
        self.assertIn('A2: Raw Measurement Data', html)

    def test_manual_appendix_labels_override_auto_labels(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
            appendix_label_config={
                'mode': 'manual',
                'manual_labels': {
                    'grain_raw_data': 'Supplement S-2',
                },
            },
        )

        self.assertIn('Supplement S-2: Raw Measurement Data', html)
        self.assertNotIn('Appendix A: Raw Measurement Data', html)

    def test_single_appendix_layout_groups_sections_under_one_label(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': True,
                'gradation': False,
                'data_quality': False,
            },
            appendix_label_config={
                'layout': 'single',
                'mode': 'manual',
                'single_label': 'Appendix QA',
            },
        )

        self.assertIn('Appendix QA</h3>', html)
        self.assertIn('Detailed Percentile Data</h4>', html)
        self.assertIn('Raw Measurement Data</h4>', html)
        self.assertNotIn('Appendix QA: Raw Measurement Data', html)

    def test_combined_report_propagates_appendix_label_config(self):
        html = self.generator.generate_combined_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.35,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': True,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
                'k_statistics': False,
            },
            appendix_label_config={
                'mode': 'manual',
                'manual_labels': {
                    'grain_raw_data': 'Client Appendix R1',
                },
            },
        )

        self.assertIn('Client Appendix R1: Raw Measurement Data', html)

    def test_docx_export_generates_editable_document_bytes(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': True,
                'methodology': False,
                'results': True,
                'plots': False,
                'raw_data': False,
                'interpretation': False,
                'percentiles': True,
                'gradation': False,
                'data_quality': False,
            },
        )

        docx_bytes = self.generator.generate_docx_from_html(html)

        self.assertTrue(docx_bytes.startswith(b'PK'))
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
            document_xml = archive.read('word/document.xml').decode('utf-8')

        self.assertIn('Grain Size Analysis Report', document_xml)
        self.assertIn('Detailed Percentile Data', document_xml)

    def test_docx_export_switches_large_plot_pages_to_landscape(self):
        from docx import Document

        pixel_png = (
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+'
            'A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        html = f'''<html><body>
        <p>Portrait before</p>
        <div class="comparison-plot-page landscape-plot-page">
          <h2>Landscape plot</h2>
          <div class="plot-container">
            <img src="data:image/png;base64,{pixel_png}" alt="Comparison plot">
          </div>
        </div>
        <p>Portrait after</p>
        </body></html>'''

        document = Document(io.BytesIO(self.generator.generate_docx_from_html(html)))

        self.assertEqual(len(document.sections), 3)
        page_shapes = [
            (round(section.page_width.inches, 1), round(section.page_height.inches, 1))
            for section in document.sections
        ]
        self.assertEqual(page_shapes, [(8.3, 11.7), (11.7, 8.3), (8.3, 11.7)])
        self.assertAlmostEqual(document.inline_shapes[0].width.inches, 10.2, places=1)

    def test_print_css_removes_portrait_body_width_from_landscape_pages(self):
        html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': False,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
        )

        self.assertIn('width: auto !important;', html)
        self.assertIn('max-width: none !important;', html)
        self.assertIn('padding: 0 !important;', html)

    def test_grain_size_report_plot_uses_live_plot_context(self):
        calls = []

        def capture_renderer(ax, particle_sizes, percent_passing, **kwargs):
            calls.append(kwargs)
            ax.plot(particle_sizes, percent_passing, label=kwargs.get('sample_name'))

        context = {
            'show_d_lines': False,
            'show_markers': False,
            'show_grid': False,
            'show_legend': False,
            'show_title': True,
            'plot_title': 'Custom report plot',
            'show_x_label': False,
            'plot_x_label': 'Custom diameter',
            'show_y_label': True,
            'plot_y_label': 'Custom passing',
        }

        with patch('plot_export.render_grain_size_distribution', side_effect=capture_renderer):
            html = self.generator.generate_grain_size_report(
                self.dataset,
                sections={
                    'cover_page': False,
                    'executive_summary': False,
                    'methodology': False,
                    'results': False,
                    'plots': True,
                    'raw_data': False,
                    'interpretation': False,
                    'percentiles': False,
                    'gradation': False,
                    'data_quality': False,
                },
                plot_context=context,
            )

        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertFalse(call['show_d_lines'])
        self.assertFalse(call['show_markers'])
        self.assertFalse(call['show_grid'])
        self.assertFalse(call['show_legend'])
        self.assertTrue(call['show_title'])
        self.assertEqual(call['title'], 'Custom report plot')
        self.assertFalse(call['show_x_label'])
        self.assertEqual(call['x_label'], 'Custom diameter')
        self.assertTrue(call['show_y_label'])
        self.assertEqual(call['y_label'], 'Custom passing')
        self.assertIn('data:image/png;base64,', html)

    def test_k_value_report_uses_ok_only_geometric_summary(self):
        results = [
            KCalculationResult(
                method_name='Hazen',
                k_value=1.0e-4,
                formula_used='',
                status=CalculationStatus.OK,
                status_message='',
                conditions_met=True,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D10',
            ),
            KCalculationResult(
                method_name='Kruger',
                k_value=1.0e-2,
                formula_used='',
                status=CalculationStatus.WARNING,
                status_message='outside recommended range',
                conditions_met=False,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D50',
            ),
            KCalculationResult(
                method_name='USBR',
                k_value=4.0e-4,
                formula_used='',
                status=CalculationStatus.OK,
                status_message='',
                conditions_met=True,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D20',
            ),
        ]

        html = self.generator.generate_k_value_report(
            self.dataset,
            results,
            temperature=20.0,
            porosity=0.35,
            sections={
                'cover_page': False,
                'executive_summary': True,
                'methodology': False,
                'results': True,
                'plots': False,
                'interpretation': False,
                'k_statistics': False,
            },
        )

        self.assertIn('Geometric Mean K:</strong> 2.00e-04 m/s', html)
        self.assertIn('from 2 OK methods', html)
        self.assertIn('K Arithmetic Mean', html)

    def test_reports_show_effective_porosity_and_source(self):
        self.dataset.calculated_porosity = 0.3123
        self.dataset.current_porosity = 0.5000
        self.dataset.porosity = 0.3500

        grain_html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'raw_data': False,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
        )
        k_html = self.generator.generate_k_value_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.5,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'interpretation': False,
                'k_statistics': False,
            },
        )

        self.assertIn('<div class="metadata-value">0.5000</div>', grain_html)
        self.assertIn('Porosity Source:', grain_html)
        self.assertIn('Manual override', grain_html)
        self.assertIn('<div class="metadata-value">0.5000</div>', k_html)
        self.assertIn('Porosity Source:', k_html)

    def test_k_value_report_can_show_method_table_without_results_section(self):
        html = self.generator.generate_k_value_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.35,
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'interpretation': False,
                'k_statistics': True,
            },
        )

        self.assertIn('K-Value Results', html)
        self.assertIn('K-Value Calculations by Method', html)
        self.assertIn('Hazen', html)
        self.assertNotIn('Results & Analysis', html)

    def test_k_focus_comparison_report_includes_k_method_table_without_results_section(self):
        sample_b = build_dataset('Sample B')
        results_b = [
            KCalculationResult(
                method_name='USBR',
                k_value=2.0e-4,
                formula_used='k = f(d20)',
                status=CalculationStatus.OK,
                status_message='',
                conditions_met=True,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D20',
            ),
        ]

        html = self.generator.generate_comparison_report(
            [self.dataset, sample_b],
            sections={
                'cover_page': False,
                'executive_summary': False,
                'methodology': False,
                'results': False,
                'plots': False,
                'interpretation': False,
                'k_statistics': True,
            },
            sample_details=[
                {
                    'label': 'Sample A',
                    'dataset': self.dataset,
                    'k_results': self.results,
                    'temperature': 20.0,
                    'porosity': 0.35,
                },
                {
                    'label': 'Sample B',
                    'dataset': sample_b,
                    'k_results': results_b,
                    'temperature': 20.0,
                    'porosity': 0.35,
                },
            ],
        )

        self.assertIn('K-Value Calculations by Dataset and Method', html)
        self.assertIn('Permeability Classification Summary', html)
        self.assertIn('Sample A', html)
        self.assertIn('Sample B', html)
        self.assertIn('Hazen', html)
        self.assertIn('USBR', html)
        self.assertNotIn('Sample Overview', html)

    def test_comparison_report_uses_grouped_k_scope_for_summary_and_boxplot(self):
        sample_b = build_dataset('Sample B')
        results_b = [
            KCalculationResult(
                method_name='USBR',
                k_value=2.0e-4,
                formula_used='k = f(d20)',
                status=CalculationStatus.OK,
                status_message='',
                conditions_met=True,
                temperature=20.0,
                porosity=0.35,
                grain_size_used='D20',
            ),
        ]

        with patch('plot_export.export_distribution_overlay', return_value='grain-plot'), \
             patch('plot_export.export_reliability_matrix', return_value=''), \
             patch('plot_export.export_k_scope_boxplot', return_value='scope-plot') as boxplot:
            html = self.generator.generate_comparison_report(
                [self.dataset, sample_b],
                sections={
                    'cover_page': False,
                    'executive_summary': False,
                    'methodology': False,
                    'results': True,
                    'plots': True,
                    'interpretation': False,
                    'k_statistics': True,
                },
                sample_details=[
                    {
                        'label': 'Sample A',
                        'dataset': self.dataset,
                        'k_results': self.results,
                        'group_name': 'Layer A',
                        'temperature': 20.0,
                        'porosity': 0.35,
                    },
                    {
                        'label': 'Sample B',
                        'dataset': sample_b,
                        'k_results': results_b,
                        'group_name': 'Layer B',
                        'temperature': 20.0,
                        'porosity': 0.35,
                    },
                ],
            )

        self.assertIn('K-Value Aggregate Summary', html)
        self.assertIn('Layer A', html)
        self.assertIn('Layer B', html)
        self.assertIn('Included K cells', html)
        self.assertIn('scope-plot', html)
        series = boxplot.call_args[0][0]
        self.assertEqual([label for label, _values in series], ['Overall', 'Layer A', 'Layer B'])

    def test_large_grain_parameter_comparison_uses_long_table(self):
        datasets = [build_dataset(f'Sample {idx:02d}') for idx in range(1, 10)]
        labels = [dataset.sample_name for dataset in datasets]

        html = self.generator._create_grain_parameters_comparison_table(datasets, labels)

        self.assertIn('<th>Sample</th>', html)
        self.assertIn('<th>Value</th>', html)
        self.assertIn('D10 (mm) summary', html)
        self.assertNotIn('table-wide', html)

    def test_generated_reports_do_not_emit_literal_page_number_placeholder(self):
        grain_html = self.generator.generate_grain_size_report(
            self.dataset,
            sections={
                'cover_page': False,
                'executive_summary': True,
                'methodology': False,
                'results': True,
                'plots': False,
                'raw_data': False,
                'interpretation': False,
                'percentiles': False,
                'gradation': False,
                'data_quality': False,
            },
        )
        comparison_html = self.generator.generate_comparison_report(
            [self.dataset, build_dataset('Sample B')],
            sections={
                'cover_page': False,
                'executive_summary': True,
                'methodology': False,
                'results': True,
                'plots': False,
                'interpretation': False,
                'k_statistics': True,
            },
            sample_details=[
                {
                    'label': 'Sample A',
                    'dataset': self.dataset,
                    'k_results': self.results,
                    'temperature': 20.0,
                    'porosity': 0.35,
                },
                {
                    'label': 'Sample B',
                    'dataset': build_dataset('Sample B'),
                    'k_results': self.results,
                    'temperature': 20.0,
                    'porosity': 0.35,
                },
            ],
        )

        self.assertNotIn('Page #', grain_html)
        self.assertNotIn('Page #', comparison_html)

    def test_report_generation_is_repeatable_on_same_generator(self):
        sections = {
            'cover_page': False,
            'executive_summary': True,
            'methodology': False,
            'results': True,
            'plots': False,
            'interpretation': False,
            'k_statistics': True,
        }

        first = self.generator.generate_k_value_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.35,
            sections=sections,
        )
        second = self.generator.generate_k_value_report(
            self.dataset,
            self.results,
            temperature=20.0,
            porosity=0.35,
            sections=sections,
        )

        self.assertIn('Hydraulic Conductivity Analysis Report', first)
        self.assertIn('Hydraulic Conductivity Analysis Report', second)
        self.assertIn('K-Value Calculations by Method', second)


if __name__ == '__main__':
    unittest.main(verbosity=2)
