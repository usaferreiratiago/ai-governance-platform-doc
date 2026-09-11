"""
Initialize the database with all required tables for the AI Governance Platform.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from streamlit_app.db import engine, init_db, Base

# SQL statements to create all tables
sql_statements = [
    # ============================================================
    # 1. USERS - User management
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        role TEXT DEFAULT 'VIEWER',
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 2. AUDIT LOGS - Audit trail for all actions
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_time TEXT NOT NULL,
        user_name TEXT NOT NULL,
        action TEXT NOT NULL,
        entity TEXT,
        entity_id TEXT,
        details TEXT,
        ip_address TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 3. PROMPTS - System prompts and versions
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS prompts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        content TEXT NOT NULL,
        description TEXT,
        version TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 4. SEMANTIC MODELS - Governed semantic models
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS semantic_models (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        content TEXT,
        version TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 5. QUERY EXECUTIONS - History of all queries
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS query_executions (
        id TEXT PRIMARY KEY,
        question TEXT NOT NULL,
        generated_sql TEXT,
        execution_time_ms INTEGER,
        status TEXT,
        result_rows INTEGER,
        model_used TEXT,
        user_name TEXT,
        error_message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 6. BENCHMARK RUNS - Model performance benchmarks
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS benchmark_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_name TEXT NOT NULL,
        score REAL,
        accuracy REAL,
        precision REAL,
        recall REAL,
        f1_score REAL,
        details TEXT,
        test_size INTEGER,
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 7. GUARDRAILS - Mandatory filters and rules
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS guardrails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        measure_name TEXT NOT NULL,
        mandatory_filters TEXT,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 8. GLOSSARY TERMS - Business glossary
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS glossary_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_term TEXT NOT NULL UNIQUE,
        description TEXT,
        synonyms TEXT,
        category TEXT,
        table_name TEXT,
        field_name TEXT,
        is_certified BOOLEAN DEFAULT 0,
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 9. METADATA TABLES - Table metadata
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS metadata_tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        business_name TEXT,
        description TEXT,
        table_type TEXT,
        schema_name TEXT,
        owner TEXT,
        is_certified BOOLEAN DEFAULT 0,
        row_count_estimate INTEGER,
        refresh_frequency TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 10. METADATA COLUMNS - Column metadata
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS metadata_columns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER,
        name TEXT NOT NULL,
        business_name TEXT,
        description TEXT,
        data_type TEXT,
        is_primary_key BOOLEAN DEFAULT 0,
        is_foreign_key BOOLEAN DEFAULT 0,
        references_table TEXT,
        references_column TEXT,
        nullable BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (table_id) REFERENCES metadata_tables(id)
    );
    ''',
    
    # ============================================================
    # 11. RELATIONSHIPS - Table relationships
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_table TEXT NOT NULL,
        from_column TEXT NOT NULL,
        to_table TEXT NOT NULL,
        to_column TEXT NOT NULL,
        cardinality TEXT,
        relationship_type TEXT,
        is_active BOOLEAN DEFAULT 1,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 12. LLM REQUESTS - All LLM interactions
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS llm_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT UNIQUE,
        question TEXT NOT NULL,
        response TEXT,
        model_used TEXT,
        tokens_input INTEGER,
        tokens_output INTEGER,
        execution_time_ms INTEGER,
        status TEXT,
        user_name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''',
    
    # ============================================================
    # 13. SYSTEM CONFIG - Application configuration
    # ============================================================
    '''
    CREATE TABLE IF NOT EXISTS system_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT UNIQUE NOT NULL,
        config_value TEXT,
        description TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    '''
]

def init_tables():
    """Create all tables if they don't exist."""
    with engine.begin() as conn:
        for sql in sql_statements:
            try:
                conn.execute(text(sql))
            except Exception as e:
                print(f"⚠️ Warning: {e}")
    print("✅ Tables created successfully!")

def insert_default_data():
    """Insert default data for system configuration and initial setup."""
    with engine.begin() as conn:
        # Insert default system config
        conn.execute(
            text("""
                INSERT OR IGNORE INTO system_config (config_key, config_value, description)
                VALUES 
                    ('app_name', 'AI Governance Platform', 'Application name'),
                    ('app_version', '1.0.0', 'Application version'),
                    ('default_model', 'gemini-3.6-flash', 'Default LLM model'),
                    ('mock_mode', 'true', 'Mock mode for testing'),
                    ('audit_enabled', 'true', 'Enable audit logging')
            """)
        )
        
        # Insert default admin user if not exists
        conn.execute(
            text("""
                INSERT OR IGNORE INTO users (id, username, email, password_hash, full_name, role)
                VALUES 
                    ('user-admin', 'admin', 'admin@company.com', 'hashed_password_here', 'System Administrator', 'ADMIN')
            """)
        )
        
        # Insert default prompt if not exists
        conn.execute(
            text("""
                INSERT OR IGNORE INTO prompts (name, content, description, version, is_active, created_by)
                VALUES (
                    'system_prompt_v1',
                    '# Enterprise Analytics Assistant\n\nYou are the official enterprise analytics assistant.\nUse only approved semantic-model objects.\nNever invent measures, tables, columns, or relationships.\n\nIf information is unavailable, respond exactly:\nThe requested information is not available in the approved semantic model.',
                    'Default system prompt for the AI Governance Platform',
                    '1.0.0',
                    1,
                    'system'
                )
            """)
        )
        
        # Insert default guardrails
        conn.execute(
            text("""
                INSERT OR IGNORE INTO guardrails (measure_name, mandatory_filters, description, is_active, created_by)
                VALUES 
                    ('Net Revenue', 'Date', 'Date filter is mandatory for Net Revenue', 1, 'system'),
                    ('Gross Margin %', 'Date', 'Date filter is mandatory for Gross Margin %', 1, 'system'),
                    ('Inventory Value', 'Date, Warehouse', 'Date and Warehouse filters are mandatory for Inventory Value', 1, 'system'),
                    ('Return Rate', 'Date', 'Date filter is mandatory for Return Rate', 1, 'system')
            """)
        )
        
        # Insert default glossary terms
        conn.execute(
            text("""
                INSERT OR IGNORE INTO glossary_terms (business_term, description, synonyms, category, is_certified, created_by)
                VALUES 
                    ('Net Revenue', 'Revenue after discounts, returns, and allowances', 'revenue,sales,turnover', 'Financial', 1, 'system'),
                    ('Gross Margin %', 'Gross profit divided by net revenue', 'margin,gross margin,profitability', 'Financial', 1, 'system'),
                    ('Average Unit Price', 'Average selling price per unit sold', 'unit price,average price', 'Commercial', 1, 'system'),
                    ('Inventory Value', 'Monetary value of inventory on hand', 'stock value,inventory', 'Inventory', 1, 'system'),
                    ('Return Rate', 'Percentage of sold units that were returned', 'returns,refund rate', 'Operational', 1, 'system')
            """)
        )
        
        print("✅ Default data inserted successfully!")

def create_indexes():
    """Create indexes for better performance."""
    with engine.begin() as conn:
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_name)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_query_executions_created ON query_executions(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_query_executions_user ON query_executions(user_name)",
            "CREATE INDEX IF NOT EXISTS idx_llm_requests_created ON llm_requests(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_guardrails_measure ON guardrails(measure_name)",
            "CREATE INDEX IF NOT EXISTS idx_semantic_models_active ON semantic_models(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_metadata_tables_name ON metadata_tables(name)",
        ]
        
        for index in indexes:
            try:
                conn.execute(text(index))
            except Exception as e:
                print(f"⚠️ Index warning: {e}")
    
    print("✅ Indexes created successfully!")

def init_db_full():
    """Initialize the complete database."""
    print("🚀 Initializing AI Governance Platform Database...")
    print("=" * 50)
    
    # Initialize database directory and base tables
    init_db()
    
    # Create all tables
    init_tables()
    
    # Create indexes
    create_indexes()
    
    # Insert default data
    insert_default_data()
    
    print("=" * 50)
    print("✅ Database initialized successfully!")
    print(f"📁 Database location: {ROOT_DIR / 'db' / 'governance.db'}")
    print("\n📊 Tables created:")
    print("   - users, audit_logs, prompts, semantic_models")
    print("   - query_executions, benchmark_runs, guardrails")
    print("   - glossary_terms, metadata_tables, metadata_columns")
    print("   - relationships, llm_requests, system_config")

if __name__ == '__main__':
    init_db_full()