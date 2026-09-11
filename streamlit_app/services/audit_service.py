"""
Audit service for logging and retrieving user actions.
"""
from datetime import datetime
from sqlalchemy import text
from streamlit_app.db import engine


def log_event(
    user_name: str, 
    action: str, 
    entity: str = "", 
    entity_id: str = "", 
    details: str = "",
    ip_address: str = ""
):
    """
    Log an event to the audit trail.
    
    Args:
        user_name: Name of the user performing the action
        action: Description of the action
        entity: Entity type (e.g., 'user', 'prompt', 'benchmark')
        entity_id: ID of the entity being acted upon
        details: Additional details about the action
        ip_address: IP address of the user
    """
    event_time = datetime.now().isoformat()
    
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO audit_logs (
                    event_time, user_name, action, entity, entity_id, details, ip_address
                )
                VALUES (
                    :event_time, :user_name, :action, :entity, :entity_id, :details, :ip_address
                )
            """),
            {
                "event_time": event_time,
                "user_name": user_name,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "details": details,
                "ip_address": ip_address
            }
        )


def get_audit_logs(
    limit: int = 100, 
    user_name: str = None, 
    action: str = None,
    entity: str = None,
    start_date: str = None,
    end_date: str = None
):
    """
    Retrieve audit logs with optional filters.
    
    Args:
        limit: Maximum number of logs to retrieve
        user_name: Filter by user name
        action: Filter by action
        entity: Filter by entity type
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
    
    Returns:
        List of audit log entries as dictionaries
    """
    query = """
        SELECT 
            id,
            event_time, 
            user_name, 
            action, 
            entity, 
            entity_id, 
            details,
            ip_address,
            created_at
        FROM audit_logs
        WHERE 1=1
    """
    params = {}
    
    if user_name:
        query += " AND user_name = :user_name"
        params["user_name"] = user_name
    
    if action:
        query += " AND action = :action"
        params["action"] = action
    
    if entity:
        query += " AND entity = :entity"
        params["entity"] = entity
    
    if start_date:
        query += " AND created_at >= :start_date"
        params["start_date"] = start_date
    
    if end_date:
        query += " AND created_at <= :end_date"
        params["end_date"] = end_date
    
    query += " ORDER BY event_time DESC LIMIT :limit"
    params["limit"] = limit
    
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]


def get_audit_statistics():
    """
    Get statistics about audit logs.
    
    Returns:
        Dict with audit statistics
    """
    with engine.connect() as conn:
        # Total logs
        total = conn.execute(text("SELECT COUNT(*) FROM audit_logs")).fetchone()[0]
        
        # Logs by action (top 10)
        actions = conn.execute(
            text("""
                SELECT action, COUNT(*) as count 
                FROM audit_logs 
                GROUP BY action 
                ORDER BY count DESC 
                LIMIT 10
            """)
        ).fetchall()
        
        # Logs by user (top 10)
        users = conn.execute(
            text("""
                SELECT user_name, COUNT(*) as count 
                FROM audit_logs 
                GROUP BY user_name 
                ORDER BY count DESC 
                LIMIT 10
            """)
        ).fetchall()
        
        # Logs by date (last 7 days)
        dates = conn.execute(
            text("""
                SELECT 
                    DATE(created_at) as date, 
                    COUNT(*) as count 
                FROM audit_logs 
                WHERE created_at >= DATE('now', '-7 days')
                GROUP BY DATE(created_at) 
                ORDER BY date DESC
            """)
        ).fetchall()
        
        # Logs by entity
        entities = conn.execute(
            text("""
                SELECT entity, COUNT(*) as count 
                FROM audit_logs 
                WHERE entity IS NOT NULL AND entity != ''
                GROUP BY entity 
                ORDER BY count DESC 
                LIMIT 10
            """)
        ).fetchall()
        
        # Recent activity
        recent = conn.execute(
            text("""
                SELECT event_time, user_name, action 
                FROM audit_logs 
                ORDER BY event_time DESC 
                LIMIT 10
            """)
        ).fetchall()
        
        return {
            "total": total,
            "actions": [{"action": a[0], "count": a[1]} for a in actions],
            "users": [{"user": u[0], "count": u[1]} for u in users],
            "dates": [{"date": d[0], "count": d[1]} for d in dates],
            "entities": [{"entity": e[0], "count": e[1]} for e in entities],
            "recent": [{"event_time": r[0], "user_name": r[1], "action": r[2]} for r in recent]
        }


def clear_old_logs(days: int = 30):
    """
    Clear audit logs older than specified days.
    
    Args:
        days: Number of days to keep (logs older than this will be deleted)
    
    Returns:
        int: Number of rows deleted
    """
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                DELETE FROM audit_logs 
                WHERE created_at < DATE('now', :days)
            """),
            {"days": f"-{days} days"}
        )
        return result.rowcount


def search_audit_logs(search_term: str, limit: int = 50):
    """
    Search audit logs for a specific term.
    
    Args:
        search_term: Term to search for
        limit: Maximum number of results
    
    Returns:
        List of matching audit log entries
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT 
                    event_time, 
                    user_name, 
                    action, 
                    entity, 
                    entity_id, 
                    details
                FROM audit_logs
                WHERE 
                    user_name LIKE :search_term
                    OR action LIKE :search_term
                    OR entity LIKE :search_term
                    OR entity_id LIKE :search_term
                    OR details LIKE :search_term
                ORDER BY event_time DESC
                LIMIT :limit
            """),
            {"search_term": f"%{search_term}%", "limit": limit}
        )
        return [dict(row._mapping) for row in result]


def get_user_activity_summary(user_name: str, days: int = 30):
    """
    Get a summary of a specific user's activity.
    
    Args:
        user_name: Username to analyze
        days: Number of days to look back
    
    Returns:
        Dict with user activity summary
    """
    with engine.connect() as conn:
        # Total actions
        total = conn.execute(
            text("""
                SELECT COUNT(*) FROM audit_logs 
                WHERE user_name = :user_name 
                AND created_at >= DATE('now', :days)
            """),
            {"user_name": user_name, "days": f"-{days} days"}
        ).fetchone()[0]
        
        # Actions by type
        actions = conn.execute(
            text("""
                SELECT action, COUNT(*) as count 
                FROM audit_logs 
                WHERE user_name = :user_name 
                AND created_at >= DATE('now', :days)
                GROUP BY action 
                ORDER BY count DESC
            """),
            {"user_name": user_name, "days": f"-{days} days"}
        ).fetchall()
        
        # Daily activity
        daily = conn.execute(
            text("""
                SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM audit_logs 
                WHERE user_name = :user_name 
                AND created_at >= DATE('now', :days)
                GROUP BY DATE(created_at) 
                ORDER BY date DESC
            """),
            {"user_name": user_name, "days": f"-{days} days"}
        ).fetchall()
        
        return {
            "total_actions": total,
            "actions": [{"action": a[0], "count": a[1]} for a in actions],
            "daily_activity": [{"date": d[0], "count": d[1]} for d in daily]
        }


# ---------------------------------------------------------------------
# CLI Utility
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import json
    
    print("📊 Audit Service Test")
    print("=" * 50)
    
    # Test: Log an event
    print("\n📝 Logging test event...")
    log_event(
        user_name="test_user",
        action="TEST_ACTION",
        entity="Test",
        entity_id="test-001",
        details="Test event from CLI",
        ip_address="127.0.0.1"
    )
    print("✅ Event logged!")
    
    # Test: Get recent logs
    print("\n📋 Recent logs:")
    logs = get_audit_logs(limit=5)
    for log in logs:
        print(f"  {log['event_time']} - {log['user_name']}: {log['action']}")
    
    # Test: Get statistics
    print("\n📊 Statistics:")
    stats = get_audit_statistics()
    print(f"  Total logs: {stats['total']}")
    print(f"  Top actions: {stats['actions'][:3]}")
    print("✅ Audit service working correctly!")