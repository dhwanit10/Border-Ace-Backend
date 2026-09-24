import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.database import engine, Base
from app.models import (
    User, Document, 
    VerificationEntry, Risk, System, Session
      # Import enums
)
from app.core.bootstrap import initialize_database
from sqlalchemy import text

def init_database():
    """Initialize or reset the database with new schema"""
    print("🔄 Creating tables and bootstrap user with updated schema...")
    
    # Create all tables (this will not drop existing tables)
    initialize_database()
    
    print("✅ Tables created/verified!")
    
    
def reset_database():
    """Drop and recreate all tables"""
    print("⚠️  WARNING: This will delete ALL data!")
    confirm = input("Are you sure you want to continue? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("❌ Operation cancelled.")
        return
    
    print("🔄 Dropping all tables...")
    
    # Drop tables with CASCADE to handle dependencies
    with engine.connect() as conn:
        conn.execute(text("""
            DO $$ 
            DECLARE 
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        """))
        conn.commit()
    
    print("✅ Tables dropped!")
    
    # Drop enum types if they exist
    with engine.connect() as conn:
        conn.execute(text("DROP TYPE IF EXISTS usertype CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS documenttypeenum CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS userstatus CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS riskstatus CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS systemstatus CASCADE"))
        conn.commit()
    
    print("✅ Enums dropped!")
    
    # Recreate tables
    init_database()

def show_tables():
    """Show current tables in database"""
    print("\n📊 Current tables in database:")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        if tables:
            for table in tables:
                # Get row count for each table
                count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = count_result.scalar()
                print(f"  - {table} ({count} rows)")
        else:
            print("  No tables found. Run 'python scripts/init_db.py' to create tables.")

def show_schema():
    """Show detailed schema of all tables"""
    print("\n📋 Database Schema:")
    with engine.connect() as conn:
        # Get all tables
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        
        for table in tables:
            print(f"\n📌 Table: {table}")
            print("-" * 50)
            
            # Get columns
            columns = conn.execute(text(f"""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """))
            
            for col in columns:
                null_str = "NULL" if col[2] == 'YES' else "NOT NULL"
                default_str = f" DEFAULT {col[3]}" if col[3] else ""
                print(f"  {col[0]:<25} {col[1]:<20} {null_str}{default_str}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Database management script')
    parser.add_argument('--reset', action='store_true', 
                       help='Reset database (drop and recreate)')
    parser.add_argument('--show', action='store_true',
                       help='Show current tables')
    parser.add_argument('--schema', action='store_true',
                       help='Show detailed schema')
    parser.add_argument('--force', action='store_true',
                       help='Force reset without confirmation')
    args = parser.parse_args()
    
    if args.reset:
        if args.force:
            print("⚠️  Force reset enabled - skipping confirmation")
            confirm = 'yes'
        else:
            confirm = input("⚠️  This will DELETE ALL DATA. Are you sure? (yes/no): ")
        
        if confirm.lower() == 'yes':
            reset_database()
        else:
            print("❌ Operation cancelled.")
    elif args.show:
        show_tables()
    elif args.schema:
        show_schema()
    else:
        init_database()