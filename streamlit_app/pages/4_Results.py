import sys
from pathlib import Path

# Ensure project root is available when Streamlit runs pages/*
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from streamlit_app.components import render_header

# Page configuration
st.set_page_config(
    page_title='Evaluation Results',
    page_icon='📊',
    layout='wide',
)

# Render Power BI logo + application header
render_header()

st.header('Evaluation Results')
st.caption('Review benchmark execution results and governance quality metrics.')

results_file = ROOT_DIR / 'evaluation' / 'results.csv'

if results_file.exists():
    try:
        df = pd.read_csv(results_file)

        st.success(f'Loaded results file: {results_file.name}')

        # Summary metrics
        total_tests = len(df)

        if 'passed' in df.columns and total_tests > 0:
            accuracy = float(df['passed'].mean())
            passed_tests = int(df['passed'].sum())
            failed_tests = total_tests - passed_tests
        else:
            accuracy = 0.0
            passed_tests = 0
            failed_tests = total_tests

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric('Total Tests', total_tests)

        with col2:
            st.metric('Passed', passed_tests)

        with col3:
            st.metric('Accuracy', f'{accuracy:.2%}')

        st.divider()

        # Governance status
        st.subheader('Governance Status')

        if accuracy >= 0.85:
            st.success(
                'Benchmark accuracy is above the acceptance threshold (≥ 85%).'
            )
        else:
            st.error(
                'Benchmark accuracy is below the acceptance threshold (85%).'
            )

        st.divider()

        # Results table
        st.subheader('Detailed Results')

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # Download section
        st.subheader('Export Results')

        csv_bytes = df.to_csv(index=False).encode('utf-8')

        st.download_button(
            label='Download CSV',
            data=csv_bytes,
            file_name='benchmark_results.csv',
            mime='text/csv',
            use_container_width=True,
        )

        st.divider()

        # Quick insights
        st.subheader('Quick Insights')

        if 'question' in df.columns and 'passed' in df.columns:
            failed_df = df[df['passed'] == False]  # noqa: E712

            if not failed_df.empty:
                st.warning(f'{len(failed_df)} benchmark(s) failed validation.')

                for _, row in failed_df.head(5).iterrows():
                    st.markdown(f"- **Failed:** {row['question']}")
            else:
                st.success('All benchmark questions passed validation.')

    except Exception as exc:
        st.error(f'Failed to load evaluation results: {exc}')

else:
    st.warning('No evaluation results found. Run benchmarks first.')

    st.code(
        'python evaluation/run_benchmarks.py',
        language='bash',
    )

st.divider()

st.subheader('Acceptance Criteria')

st.markdown(
    '''
- **Accuracy:** ≥ 85%
- **Critical hallucinations:** 0
- **Benchmark execution:** Successful
- **Approved semantic model:** Required
- **Prompt governance:** Enabled
'''
)