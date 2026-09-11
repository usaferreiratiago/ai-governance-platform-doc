"""
Database configuration and models for the AI Governance Platform.
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from pathlib import Path
import uuid

# Ensure the db directory exists
ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / 'db'
DB_DIR.mkdir(parents=True, exist_ok=True)

# Get database URL from environment or use default
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"sqlite:///{DB_DIR / 'governance.db'}"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# ============================================================
# Helper Functions
# ============================================================
def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    unique_id = uuid.uuid4().hex[:12]
    return f"{prefix}-{unique_id}" if prefix else unique_id


# ============================================================
# Models
# ============================================================

class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True, default=lambda: generate_id("user"))
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default='VIEWER')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user")
    query_executions = relationship("QueryExecution", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.username}>"


class AuditLog(Base):
    """Audit log for tracking all user actions."""
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_time = Column(String, nullable=False, default=lambda: datetime.now().isoformat())
    user_name = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=True)
    action = Column(String, nullable=False, index=True)
    entity = Column(String, index=True)
    entity_id = Column(String)
    details = Column(Text)
    ip_address = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_name}>"


class Prompt(Base):
    """System prompts for LLM interactions."""
    __tablename__ = 'prompts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    content = Column(Text, nullable=False)
    description = Column(String)
    version = Column(String, default='1.0.0')
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Prompt {self.name} v{self.version}>"


class SemanticModel(Base):
    """Semantic model definitions and versions."""
    __tablename__ = 'semantic_models'
    
    id = Column(String, primary_key=True, default=lambda: generate_id("sm"))
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    content = Column(Text)  # JSON or YAML content
    version = Column(String, default='1.0.0')
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    query_executions = relationship("QueryExecution", back_populates="semantic_model")
    
    def __repr__(self):
        return f"<SemanticModel {self.name} v{self.version}>"


class QueryExecution(Base):
    """History of all query executions."""
    __tablename__ = 'query_executions'
    
    id = Column(String, primary_key=True, default=lambda: generate_id("qe"))
    question = Column(Text, nullable=False)
    generated_sql = Column(Text)
    execution_time_ms = Column(Integer)
    status = Column(String, index=True)
    result_rows = Column(Integer)
    model_used = Column(String)
    user_name = Column(String, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=True)
    semantic_model_id = Column(String, ForeignKey('semantic_models.id'), nullable=True)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    # Relationships
    user = relationship("User", back_populates="query_executions")
    semantic_model = relationship("SemanticModel", back_populates="query_executions")
    
    def __repr__(self):
        return f"<QueryExecution {self.id} - {self.status}>"


class BenchmarkRun(Base):
    """Benchmark runs for model evaluation."""
    __tablename__ = 'benchmark_runs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, nullable=False, index=True)
    score = Column(Float)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    details = Column(Text)  # JSON with additional metrics
    test_size = Column(Integer)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    def __repr__(self):
        return f"<BenchmarkRun {self.model_name} - {self.score:.2f}>"


class Guardrail(Base):
    """Guardrails and mandatory filters for measures."""
    __tablename__ = 'guardrails'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    measure_name = Column(String, nullable=False, unique=True, index=True)
    mandatory_filters = Column(String)  # Comma-separated list
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Guardrail {self.measure_name}>"


class GlossaryTerm(Base):
    """Business glossary terms."""
    __tablename__ = 'glossary_terms'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    business_term = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text)
    synonyms = Column(String)  # Comma-separated list
    category = Column(String, index=True)
    table_name = Column(String)
    field_name = Column(String)
    is_certified = Column(Boolean, default=False, index=True)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<GlossaryTerm {self.business_term}>"


class MetadataTable(Base):
    """Metadata for database tables."""
    __tablename__ = 'metadata_tables'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False, index=True)
    business_name = Column(String)
    description = Column(Text)
    table_type = Column(String)  # Fact, Dimension, etc.
    schema_name = Column(String, default='dbo')
    owner = Column(String)
    is_certified = Column(Boolean, default=False, index=True)
    row_count_estimate = Column(Integer)
    refresh_frequency = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    columns = relationship("MetadataColumn", back_populates="table")
    
    def __repr__(self):
        return f"<MetadataTable {self.name}>"


class MetadataColumn(Base):
    """Metadata for table columns."""
    __tablename__ = 'metadata_columns'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey('metadata_tables.id'), nullable=False)
    name = Column(String, nullable=False)
    business_name = Column(String)
    description = Column(Text)
    data_type = Column(String)
    is_primary_key = Column(Boolean, default=False)
    is_foreign_key = Column(Boolean, default=False)
    references_table = Column(String)
    references_column = Column(String)
    nullable = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    table = relationship("MetadataTable", back_populates="columns")
    
    def __repr__(self):
        return f"<MetadataColumn {self.table_id}.{self.name}>"


class Relationship(Base):
    """Relationships between tables."""
    __tablename__ = 'relationships'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_table = Column(String, nullable=False, index=True)
    from_column = Column(String, nullable=False)
    to_table = Column(String, nullable=False, index=True)
    to_column = Column(String, nullable=False)
    cardinality = Column(String)  # OneToOne, OneToMany, ManyToOne, ManyToMany
    relationship_type = Column(String)  # Dimension, Fact, etc.
    is_active = Column(Boolean, default=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Relationship {self.from_table}->{self.to_table}>"


class LLMRequest(Base):
    """All LLM interaction logs."""
    __tablename__ = 'llm_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, unique=True, default=lambda: generate_id("llm"))
    question = Column(Text, nullable=False)
    response = Column(Text)
    model_used = Column(String, index=True)
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    execution_time_ms = Column(Integer)
    status = Column(String, index=True)
    user_name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    def __repr__(self):
        return f"<LLMRequest {self.request_id} - {self.status}>"


class SystemConfig(Base):
    """System configuration settings."""
    __tablename__ = 'system_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String, unique=True, nullable=False, index=True)
    config_value = Column(String)
    description = Column(String)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<SystemConfig {self.config_key}={self.config_value}>"


# ============================================================
# Database Functions
# ============================================================

def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully!")


def get_config(key: str, default: str = None) -> str:
    """Get a configuration value from the database."""
    try:
        db = SessionLocal()
        config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        db.close()
        return config.config_value if config else default
    except Exception:
        return default


def set_config(key: str, value: str, description: str = None) -> bool:
    """Set a configuration value in the database."""
    try:
        db = SessionLocal()
        config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if config:
            config.config_value = value
            if description:
                config.description = description
        else:
            config = SystemConfig(
                config_key=key,
                config_value=value,
                description=description
            )
            db.add(config)
        db.commit()
        db.close()
        return True
    except Exception:
        return False


def log_audit_event(user_name: str, action: str, entity: str = "", 
                    entity_id: str = "", details: str = "", ip_address: str = ""):
    """Log an audit event."""
    try:
        db = SessionLocal()
        audit_log = AuditLog(
            event_time=datetime.now().isoformat(),
            user_name=user_name,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address
        )
        db.add(audit_log)
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"Error logging audit event: {e}")
        return False


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    print("🚀 Initializing database...")
    init_db()
    print("📊 Tables created:")
    for table in Base.metadata.tables.keys():
        print(f"   - {table}")
    print("✅ Done!")