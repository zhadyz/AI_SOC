"""
AI-SOC Web Dashboard
====================
Simple web interface for monitoring AI-SOC services

Run with: python dashboard/app.py
Access at: http://localhost:3000
"""

from flask import Flask, render_template, jsonify
import subprocess
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get current system status"""
    try:
        # Get Docker containers status
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{json .}}'],
            capture_output=True,
            text=True,
            timeout=5
        )

        containers = []
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        container = json.loads(line)
                        containers.append({
                            'name': container.get('Names', 'unknown'),
                            'status': container.get('Status', 'unknown'),
                            'ports': container.get('Ports', ''),
                            'state': container.get('State', 'unknown')
                        })
                    except json.JSONDecodeError:
                        continue

        # Determine overall health
        healthy_count = sum(1 for c in containers if 'healthy' in c['status'].lower() or 'up' in c['status'].lower())
        total_count = len(containers)

        overall_status = 'offline'
        if total_count > 0:
            if healthy_count == total_count:
                overall_status = 'healthy'
            elif healthy_count > 0:
                overall_status = 'partial'

        return jsonify({
            'status': overall_status,
            'containers': containers,
            'healthy_count': healthy_count,
            'total_count': total_count,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'containers': [],
            'healthy_count': 0,
            'total_count': 0
        })

@app.route('/api/logs/<container>')
def get_logs(container):
    """Get logs for a specific container"""
    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', '100', container],
            capture_output=True,
            text=True,
            timeout=5
        )

        return jsonify({
            'container': container,
            'logs': result.stdout + result.stderr,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'container': container,
            'error': str(e),
            'logs': ''
        })

if __name__ == '__main__':
    print("=" * 60)
    print("AI-SOC Dashboard Starting...")
    print("=" * 60)
    print("Access the dashboard at: http://localhost:3000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    app.run(host='0.0.0.0', port=3000, debug=False)
