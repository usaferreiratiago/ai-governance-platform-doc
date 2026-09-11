import sys
from pathlib import Path
import subprocess

# Ensure project root is available when Streamlit runs pages/*
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from streamlit_app.components import render_header
from streamlit_app.services.audit_service import log_event

# Page configuration
st.set_page_config(
    page_title='Benchmarks',
    page_icon='📈',
    layout='wide',
)

# Render Power BI logo + application header
render_header()

st.header('Benchmarks')
st.caption('Execute benchmark evaluations against the approved semantic model and LLM governance rules.')

st.info(
    'This action runs the benchmark engine and validates the current semantic model responses against the ground-truth dataset.'
)

col1, col2 = st.columns([1, 2])

with col1:
    run_button = st.button('Run Evaluation', use_container_width=True)

with col2:
    st.markdown(
        '''
**What will be executed?**

- Semantic context export
- Benchmark query execution
- Accuracy scoring
- Result persistence
- Governance validation
'''
    )

st.divider()

if run_button:
    with st.spinner('Running benchmark evaluation...'):
        try:
            result = subprocess.run(
                [sys.executable, 'evaluation/run_benchmarks.py'],
                capture_output=True,
                text=True,
                cwd=str(ROOT_DIR),
                timeout=300,
            )

            # Audit log
            log_event(
                st.session_state.get('user', 'system'),
                'Executed benchmark evaluation',
            )

            st.subheader('Execution Output')

            if result.returncode == 0:
                st.success('Benchmark execution completed successfully.')
                st.code(result.stdout or 'No output returned.', language='text')
            else:
                st.error('Benchmark execution failed.')
                st.code(result.stderr or result.stdout, language='text')

        except subprocess.TimeoutExpired:
            st.error('Benchmark execution timed out after 5 minutes.')

        except Exception as exc:
            st.error(f'Unexpected error while running benchmarks: {exc}')

st.divider()

st.subheader('Benchmark Dataset')

benchmark_file = ROOT_DIR / 'benchmarks' / 'ground_truth.csv'

if benchmark_file.exists():
    st.success(f'Loaded benchmark dataset: {benchmark_file.name}')

    with open(benchmark_file, 'r', encoding='utf-8') as f:
        preview = ''.join(f.readlines()[:10])

    st.code(preview, language='csv')
else:
    st.warning('Benchmark dataset not found.')

st.divider()

st.subheader('Expected Acceptance Criteria')

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.metric('Target Accuracy', '≥ 85%')

with col_b:
    st.metric('Critical Hallucinations', '0')

with col_c:
    st.metric('Execution Status', 'Validated')

st.divider()

st.subheader('Operational Notes')

st.markdown(
    '''
- Benchmarks should be executed after semantic-model changes.
- Re-run benchmarks after prompt modifications.
- Re-run benchmarks after DAX measure updates.
- Store benchmark results for audit and governance evidence.
- Investigate any accuracy regression before promoting changes.
'''
)