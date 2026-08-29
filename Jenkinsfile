pipeline {
    agent any

    environment {
        // ── Mirrors sosuv-workflow-api environment ──
        SEMGREP_VENV        = "/var/lib/jenkins/.semgrep-venv"
        CVSS_FAIL_THRESHOLD = "7"                 // sosuv-workflow-api uses 7 (fail on HIGH+CRITICAL)
        PIP_CACHE_DIR       = "/var/lib/jenkins/.pip-cache"

        // ── Deploy target (same pattern as sosuv) ──
        IMAGE_NAME     = "todo-api"
        CONTAINER_NAME = "todo-api"
        HOST_PORT      = "8000"
        CONTAINER_PORT = "8000"
        IMAGE_TAG      = "${env.BUILD_NUMBER ?: 'latest'}"

        DEPLOY_BRANCH  = "main"                  // sosuv uses release_10.10.9.25
    }

    stages {

        // ── Stage 1: Checkout (identical to sosuv) ──────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
                echo "✅ Branch  : ${env.BRANCH_NAME}"
                echo "✅ Commit  : ${env.GIT_COMMIT}"
                sh '''
                    echo "=== Tool versions ==="
                    python3 --version || python --version
                    pip3 --version || pip --version
                    docker --version
                    docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo "⚠️ compose not available (fallback to docker run)"
                    echo "PIP_CACHE_DIR=$PIP_CACHE_DIR"
                '''
            }
        }

        // ── Stage 2: Build & Test (mirrors sosuv mvn clean package) ───────
        stage('Build & Test') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Python Build + Unit Tests"
                    echo "========================================"

                    if [ ! -d ".venv" ]; then
                        python3 -m venv .venv
                    fi
                    . .venv/bin/activate

                    pip install --upgrade pip -q
                    pip install -r requirements.txt -q
                    pip install -r requirements-dev.txt -q || pip install pytest httpx -q

                    mkdir -p test-results
                    # ❌ STOP on failure — no "|| true" (sosuv uses -Dmaven.test.failure.ignore=true for report-only)
                    pytest -v --junitxml=test-results/junit.xml
                    echo "✅ Tests PASSED"
                    ls -lh test-results/
                '''
            }
            post {
                always  { junit testResults: 'test-results/junit.xml', allowEmptyResults: true }
                success { echo "✅ Build PASSED" }
                failure { echo "❌ Build FAILED — pytest failure → STOP" }
            }
        }

        // ── Stage 3: Semgrep SAST (IDENTICAL to sosuv-workflow-api) ─────────
        stage('Semgrep SAST') {
            steps {
                sh '''
                    set +e
                    echo "========================================"
                    echo " STAGE: Semgrep SAST Scan"
                    echo "========================================"

                    export PATH=/var/lib/jenkins/.local/bin:/var/lib/jenkins/.semgrep-venv/bin:$PATH

                    if ! command -v semgrep &>/dev/null; then
                        echo "Installing semgrep via pip..."
                        . .venv/bin/activate 2>/dev/null || true
                        python3 -m pip install semgrep --quiet --break-system-packages || \
                        python3 -m pip install semgrep --quiet || \
                        pip install semgrep --quiet || true
                    fi

                    if command -v semgrep &>/dev/null; then
                        semgrep --config=auto \
                                --json \
                                --output=semgrep-report.json \
                                --no-rewrite-rule-ids \
                                . || true
                        echo "Semgrep exit code: $?"
                        ls -lh semgrep-report.json || echo "No report generated"
                    else
                        echo "[WARN] semgrep not found — creating empty report"
                        echo '{"results":[],"paths":{"scanned":[]}}' > semgrep-report.json
                    fi
                    set -e
                '''
                // Same pattern as sosuv: catchError marks stage FAILED but continues for report
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                    sh '''
                        . .venv/bin/activate 2>/dev/null || true
                        python3 semgrep_parse.py
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'semgrep-report.json,semgrep-summary.txt', allowEmptyArchive: true
                    publishHTML([
                        allowMissing         : true,
                        alwaysLinkToLastBuild: true,
                        keepAll              : true,
                        reportDir            : '.',
                        reportFiles          : 'semgrep-summary.html',
                        reportName           : '🔒 Semgrep Report'
                    ])
                }
                success { echo '✅ Semgrep PASSED' }
                failure { echo '❌ Semgrep FAILED — fix errors before merging' }
            }
        }

        // ── Stage 4: OWASP CVE Scan (Python = pip-audit, mirrors sosuv mvn dependency-check) ──
        stage('OWASP CVE Scan') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: OWASP CVE Scan (pip-audit — Python equiv.)"
                    echo "========================================"

                    . .venv/bin/activate 2>/dev/null || true

                    if ! command -v pip-audit &>/dev/null; then
                        echo "Installing pip-audit..."
                        python3 -m pip install pip-audit --quiet --break-system-packages || \
                        pip install pip-audit --quiet || true
                    fi

                    if command -v pip-audit &>/dev/null; then
                        pip-audit --format=json --output=pip-audit-report.json || true
                        echo "✓ pip-audit scan complete"
                        ls -lh pip-audit-report.json || echo "No report file"
                        cat pip-audit-report.json | head -100 || true
                    else
                        echo "[WARN] pip-audit not found — creating empty report"
                        echo '{"dependencies":[]}' > pip-audit-report.json
                    fi
                '''
                // sosuv pattern: threshold-based fail via owasp_parse.py
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                    sh "CVSS_FAIL_THRESHOLD=${env.CVSS_FAIL_THRESHOLD} python3 safety_parse.py"
                    // also run owasp_parse for sosuv naming compatibility (same parser)
                    // sh "CVSS_FAIL_THRESHOLD=${env.CVSS_FAIL_THRESHOLD} python3 owasp_parse.py"
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'pip-audit-report.json,safety-summary.txt,owasp-summary.txt,safety-summary.html,owasp-summary.html', allowEmptyArchive: true
                    publishHTML([
                        allowMissing         : true,
                        alwaysLinkToLastBuild: true,
                        keepAll              : true,
                        reportDir            : '.',
                        reportFiles          : 'safety-summary.html',
                        reportName           : '🛡️ Safety Report'
                    ])
                    publishHTML([
                        allowMissing         : true,
                        alwaysLinkToLastBuild: true,
                        keepAll              : true,
                        reportDir            : '.',
                        reportFiles          : 'owasp-summary.html',
                        reportName           : '🛡️ OWASP Report'
                    ])
                }
                success { echo "✅ OWASP PASSED" }
                failure { echo "❌ OWASP FAILED — fix CVEs before merging" }
            }
        }

        // ── Stage 5: Docker Build ───────────────────────────────────────────
        stage('Docker Build') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Docker Build"
                    echo "========================================"
                    docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
                    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:latest
                    docker images ${IMAGE_NAME}:${IMAGE_TAG}
                    echo "✅ Docker build complete!"
                '''
            }
            post {
                success { echo "✅ Docker Build PASSED" }
                failure { echo "❌ Docker Build FAILED" }
            }
        }

        // ── Stage 6: Remove Old Container ───────────────────────────────────
        stage('Remove Old Container') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Remove Old Container"
                    echo "========================================"
                    docker stop ${CONTAINER_NAME} || true
                    docker rm -f ${CONTAINER_NAME} || true
                    docker compose down || docker-compose down || true
                    echo "✅ Old container removed"
                    docker ps -a | grep ${CONTAINER_NAME} || echo "No leftover"
                '''
            }
        }

        // ── Stage 7: Deploy New Container ───────────────────────────────────
        stage('Deploy New Container') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Deploy New Container"
                    echo "========================================"
                    # Check if compose plugin exists, fallback to docker run (Jenkins controller has no compose plugin)
                    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && [ -f "docker-compose.yml" ]; then
                        echo "Using docker compose"
                        IMAGE_TAG=${IMAGE_TAG} HOST_PORT=${HOST_PORT} docker compose up -d --build || \
                            docker run -d --name ${CONTAINER_NAME} -p ${HOST_PORT}:${CONTAINER_PORT} --restart unless-stopped ${IMAGE_NAME}:latest
                        docker compose ps 2>/dev/null || docker ps | grep ${CONTAINER_NAME} || true
                    else
                        echo "Compose not available — using docker run"
                        docker run -d --name ${CONTAINER_NAME} -p ${HOST_PORT}:${CONTAINER_PORT} --restart unless-stopped ${IMAGE_NAME}:latest
                        docker ps | grep ${CONTAINER_NAME}
                    fi
                    echo "🚀 Deploy done"
                '''
            }
            post {
                success { echo "🚀 Deploy SUCCESS" }
                failure { echo "❌ Deploy FAILED" }
            }
        }

        // ── Stage 8: Health Check → SUCCESS ─────────────────────────────────
        stage('Health Check') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Health Check"
                    echo "========================================"
                    sleep 10
                    for i in 1 2 3 4 5 6; do
                        echo "Attempt $i: curl http://localhost:${HOST_PORT}/health"
                        if curl -f --silent http://localhost:${HOST_PORT}/health; then
                            echo ""
                            echo "✅ Health check PASSED"
                            curl -s http://localhost:${HOST_PORT}/health; echo ""
                            docker ps | grep ${CONTAINER_NAME} || docker compose ps || true
                            exit 0
                        fi
                        sleep 5
                    done
                    echo "❌ Health check FAILED"
                    docker logs ${CONTAINER_NAME} || docker compose logs --tail=100 || true
                    exit 1
                '''
            }
        }
    }

    // ── Security Summary (IDENTICAL to sosuv-workflow-api post) ─────────────
    post {
        always {
            script {
                def sg    = [status: "unknown", count: "0", errors: "0", warnings: "0", rows: []]
                def owasp = [status: "unknown", count: "0", critical: "0", high: "0", medium: "0", rows: []]

                try {
                    def inRows = false
                    readFile('semgrep-summary.txt').trim().split('\n').each { line ->
                        if (line == "ROWS") { inRows = true; return }
                        if (inRows) { if (line.trim()) sg.rows << line; return }
                        if (line.startsWith('STATUS='))   sg.status   = line.split('=',2)[1]
                        if (line.startsWith('COUNT='))    sg.count    = line.split('=',2)[1]
                        if (line.startsWith('ERRORS='))   sg.errors   = line.split('=',2)[1]
                        if (line.startsWith('WARNINGS=')) sg.warnings = line.split('=',2)[1]
                    }
                } catch (e) { sg.status = "unknown" }

                try {
                    def inRows = false
                    def txt = ""
                    try { txt = readFile('owasp-summary.txt') } catch(e) { txt = readFile('safety-summary.txt') }
                    txt.trim().split('\n').each { line ->
                        if (line == "ROWS") { inRows = true; return }
                        if (inRows) { if (line.trim()) owasp.rows << line; return }
                        if (line.startsWith('STATUS='))   owasp.status   = line.split('=',2)[1]
                        if (line.startsWith('COUNT='))    owasp.count    = line.split('=',2)[1]
                        if (line.startsWith('CRITICAL=')) owasp.critical = line.split('=',2)[1]
                        if (line.startsWith('HIGH='))     owasp.high     = line.split('=',2)[1]
                        if (line.startsWith('MEDIUM='))   owasp.medium   = line.split('=',2)[1]
                    }
                } catch (e) { owasp.status = "unknown" }

                def sgIcon    = sg.status    == "fail" ? "❌" : sg.status    == "pass" ? "✅" : "⚠️"
                def owaspIcon = owasp.status == "fail" ? "❌" : owasp.status == "pass" ? "✅" : "⚠️"
                def overallFail = (sg.status == "fail" || owasp.status == "fail")

                currentBuild.description = "Sem:${sg.status.toUpperCase()} | OWASP:${owasp.status.toUpperCase()} | C:${owasp.critical} H:${owasp.high} M:${owasp.medium}"

                echo """
╔══════════════════════════════════════════════════════════════╗
║   🔐 Security Scan Results — Build #${env.BUILD_NUMBER}
╠══════════════════════════════════════════════════════════════╣
║   Scan               Status     Findings
║   ─────────────────  ─────────  ──────────────────────────
║   Semgrep SAST       ${sgIcon} ${sg.status.toUpperCase().padRight(6)}   ${sg.errors} errors, ${sg.warnings} warnings
║   OWASP CVE Check    ${owaspIcon} ${owasp.status.toUpperCase().padRight(6)}   CRITICAL:${owasp.critical}  HIGH:${owasp.high}  MEDIUM:${owasp.medium}
╚══════════════════════════════════════════════════════════════╝"""

                def sgRowsHtml = sg.rows.collect { row ->
                    def cells = row.split('\\|').collect { it.trim() }.findAll { it }
                    "<tr>${cells.collect { cell -> '<td style=\"padding:8px 12px;border-bottom:1px solid #edf2f7;font-size:13px\">' + cell + '</td>' }.join('')}</tr>"
                }.join('')

                def owaspRowsHtml = owasp.rows.collect { row ->
                    def cells = row.split('\\|').collect { it.trim() }.findAll { it }
                    "<tr>${cells.collect { cell -> '<td style=\"padding:8px 12px;border-bottom:1px solid #edf2f7;font-size:13px\">' + cell + '</td>' }.join('')}</tr>"
                }.join('')

                def overallBanner = overallFail
                    ? "<div style='background:#9b2335;color:#fff;padding:16px 24px;border-radius:8px;margin-bottom:24px'><h2 style='margin:0'>❌ Security issues found — Fix before merging</h2></div>"
                    : "<div style='background:#276749;color:#fff;padding:16px 24px;border-radius:8px;margin-bottom:24px'><h2 style='margin:0'>✅ All security checks passed — Safe to merge</h2></div>"

                def sgSection = (sg.status == "fail" && sg.rows) ? """
                    <h3 style='color:#c53030'>🔴 Code Issues (Semgrep)</h3>
                    <table style='width:100%;border-collapse:collapse;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1)'>
                      <thead><tr style='background:#edf2f7'>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>Severity</th>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>File</th>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>Rule</th>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>CWE</th>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>Fix Hint</th>
                      </tr></thead>
                      <tbody>${sgRowsHtml}</tbody>
                    </table><br>
                """ : ""

                def owaspSection = (owasp.status == "fail" && owasp.rows) ? """
                    <h3 style='color:#c53030'>🔴 Dependency Issues (OWASP)</h3>
                    <table style='width:100%;border-collapse:collapse;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1)'>
                      <thead><tr style='background:#edf2f7'>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>Severity</th>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>Library</th>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>CVE</th>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>Score</th>
                        <th style='padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568'>Suggested Fix</th>
                      </tr></thead>
                      <tbody>${owaspRowsHtml}</tbody>
                    </table><br>
                """ : ""

                def summaryHtml = """<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>
<title>Security Summary — Build #${env.BUILD_NUMBER}</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f7fafc;margin:0;padding:24px;color:#2d3748}
  table.summary{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1);margin-bottom:24px}
  table.summary th{background:#edf2f7;padding:10px 16px;text-align:left;font-size:13px;color:#4a5568}
  table.summary td{padding:12px 16px;border-bottom:1px solid #edf2f7;font-size:14px}
  table.summary tr:last-child td{border-bottom:none}
</style></head><body>
<h1 style='margin-bottom:8px'>🔐 Security Scan Results</h1>
<p style='color:#718096;margin-bottom:20px'>Build #${env.BUILD_NUMBER} — ${new Date().format('dd MMM yyyy, HH:mm')}</p>
<table class='summary'>
  <thead><tr><th>Scan</th><th>Status</th><th>Findings</th></tr></thead>
  <tbody>
    <tr><td>Semgrep SAST</td><td>${sgIcon} ${sg.status.toUpperCase()}</td><td>${sg.errors} errors, ${sg.warnings} warnings</td></tr>
    <tr><td>OWASP CVE Check</td><td>${owaspIcon} ${owasp.status.toUpperCase()}</td><td>CRITICAL: ${owasp.critical}&nbsp;&nbsp;HIGH: ${owasp.high}&nbsp;&nbsp;MEDIUM: ${owasp.medium}</td></tr>
  </tbody>
</table>
${overallBanner}
${sgSection}
${owaspSection}
</body></html>"""

                writeFile file: 'security-summary.html', text: summaryHtml
                publishHTML([
                    allowMissing         : true,
                    alwaysLinkToLastBuild: true,
                    keepAll              : true,
                    reportDir            : '.',
                    reportFiles          : 'security-summary.html',
                    reportName           : '🔐 Security Summary'
                ])
            }
        }
        success { echo "🎉 Pipeline PASSED — semgrep + owasp clean" }
        failure { echo "❌ Pipeline FAILED — fix security/test issues" }
        cleanup { cleanWs() }
    }
}
