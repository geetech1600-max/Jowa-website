from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database connection
def get_db_connection():
    try:
        # Try Render database first
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            # Fix for Render PostgreSQL
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            conn = psycopg2.connect(database_url)
            print("✅ Connected to Render PostgreSQL")
            return conn
        else:
            # Try local database
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'jowa'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres'),
                port=os.getenv('DB_PORT', '5432')
            )
            print("✅ Connected to local PostgreSQL")
            return conn
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

# Test route
@app.route('/')
def home():
    return jsonify({
        "message": "JOWA Backend API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    })

# Health check
@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            return jsonify({
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "status": "unhealthy",
                "database": "disconnected",
                "timestamp": datetime.now().isoformat()
            }), 503
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# API endpoints for website
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "status": "offline",
                "message": "Database not connected"
            }), 503
        
        cur = conn.cursor()
        
        # Get counts
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status = 'active'")
        active_jobs = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COUNT(*) FROM employers")
        total_employers = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
        total_revenue = cur.fetchone()[0] or 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            "status": "online",
            "total_users": total_users,
            "active_jobs": active_jobs,
            "total_employers": total_employers,
            "total_revenue": float(total_revenue),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Error in stats: {e}")
        return jsonify({
            "status": "offline",
            "error": str(e)
        }), 500

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    """Get all active jobs"""
    try:
        conn = get_db_connection()
        if not conn:
            # Return mock data if no database
            return jsonify([
                {
                    "id": 1,
                    "title": "Construction Worker",
                    "company": "ZamBuild Construction",
                    "location": "Lusaka",
                    "salary": "K120/day",
                    "type": "Daily",
                    "category": "construction",
                    "description": "General construction work at building sites.",
                    "posted": "2 hours ago"
                },
                {
                    "id": 2,
                    "title": "Farm Assistant",
                    "company": "Green Valley Farms",
                    "location": "Ndola",
                    "salary": "K80/day",
                    "type": "Daily",
                    "category": "farming",
                    "description": "Assist with farming activities.",
                    "posted": "5 hours ago"
                }
            ])
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT j.id, j.title, j.description, j.location, 
                   j.payment_amount, j.payment_type, j.status,
                   e.company_name,
                   CASE 
                       WHEN j.created_at > NOW() - INTERVAL '1 hour' THEN 'Just now'
                       WHEN j.created_at > NOW() - INTERVAL '24 hours' THEN 
                           EXTRACT(HOUR FROM NOW() - j.created_at) || ' hours ago'
                       ELSE TO_CHAR(j.created_at, 'DD Mon YYYY')
                   END as posted
            FROM jobs j
            LEFT JOIN employers e ON j.employer_id = e.id
            WHERE j.status = 'active'
            ORDER BY j.created_at DESC
            LIMIT 10
        """)
        
        jobs = cur.fetchall()
        cur.close()
        conn.close()
        
        jobs_list = []
        for job in jobs:
            jobs_list.append({
                "id": job[0],
                "title": job[1],
                "description": job[2] or "No description available",
                "location": job[3] or "Not specified",
                "salary": f"K{job[4]}/{job[5]}" if job[4] else "Negotiable",
                "type": job[5] or "Not specified",
                "category": "general",
                "company": job[7] or "Company not specified",
                "posted": job[8] or "Recently"
            })
        
        return jsonify(jobs_list)
        
    except Exception as e:
        print(f"Error fetching jobs: {e}")
        # Return mock data on error
        return jsonify([
            {
                "id": 1,
                "title": "Construction Worker",
                "company": "ZamBuild Construction",
                "location": "Lusaka",
                "salary": "K120/day",
                "type": "Daily",
                "category": "construction",
                "description": "General construction work at building sites.",
                "posted": "2 hours ago"
            },
            {
                "id": 2,
                "title": "Farm Assistant",
                "company": "Green Valley Farms",
                "location": "Ndola",
                "salary": "K80/day",
                "type": "Daily",
                "category": "farming",
                "description": "Assist with farming activities.",
                "posted": "5 hours ago"
            }
        ])

@app.route('/api/payments', methods=['GET'])
def get_payments():
    """Get payment history"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT purpose, amount, status, 
                   TO_CHAR(created_at, 'YYYY-MM-DD') as date,
                   transaction_id
            FROM payments
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        payments = cur.fetchall()
        cur.close()
        conn.close()
        
        payments_list = []
        for payment in payments:
            payments_list.append({
                "description": payment[0],
                "amount": f"K{payment[1]}",
                "status": payment[2],
                "date": payment[3],
                "reference": payment[4] or "N/A"
            })
        
        return jsonify(payments_list)
        
    except Exception as e:
        print(f"Error fetching payments: {e}")
        return jsonify([])

@app.route('/api/create_job', methods=['POST'])
def create_job():
    """Create a new job"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                "success": False,
                "message": "Database not connected"
            }), 503
        
        cur = conn.cursor()
        
        # Get or create employer
        phone = data.get('phone', '+260570528201')
        cur.execute("SELECT id FROM employers WHERE phone_number = %s", (phone,))
        employer = cur.fetchone()
        
        if not employer:
            cur.execute("""
                INSERT INTO employers (phone_number, company_name, business_type)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (phone, data.get('company', 'Individual Employer'), 'Various'))
            employer_id = cur.fetchone()[0]
        else:
            employer_id = employer[0]
        
        # Insert job
        cur.execute("""
            INSERT INTO jobs (employer_id, title, description, location, 
                            payment_amount, payment_type, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'active')
            RETURNING id
        """, (
            employer_id,
            data.get('title'),
            data.get('description'),
            data.get('location'),
            data.get('salary', 0),
            data.get('type', 'daily')
        ))
        
        job_id = cur.fetchone()[0]
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "job_id": job_id,
            "message": "Job created successfully"
        })
        
    except Exception as e:
        print(f"Error creating job: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    print("🚀 Starting JOWA Backend API...")
    print(f"🌐 Port: {port}")
    print(f"🔧 Debug: {debug}")
    print(f"📊 Database URL: {os.getenv('DATABASE_URL', 'Local database')}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)