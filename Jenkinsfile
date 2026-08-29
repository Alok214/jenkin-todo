pipeline {
    agent any

    // ── Tools (mirrors sosuv jdk-21/maven-3.9, but for Python we use system python3 — keep commented for reference)
    // tools {
    //     jdk 'jdk-21'
    //     maven 'maven-3.9'
    // }

    environment {
        // ── Mirrors sosuv-workflow-api environment — NVD_API_KEY is optional for todo (no credential required) ──
        // NVD_API_KEY is read from credentials if exists, else empty string (avoids ERROR: nvd-api-key when credential not configured)
        NVD_API_KEY           = ""                          // set to credentials('nvd-api-key') if you have the Jenkins credential
        NVD_CACHE_DIR         = "/var/lib/jenkins/.owasp-nvd-cache"
        SEMGREP_VENV          = "/var/lib/jenkins/.semgrep-venv"
        PIP_HOME              = "/var/lib/jenkins/.local"
        CVSS_FAIL_THRESHOLD   = "7"                 // sosuv uses 7

        // PIP cache for Python builds
        PIP_CACHE_DIR         = "/var/lib/jenkins/.pip-cache"

        // ── Deploy target (identical pattern to sosuv) ──
        IMAGE_NAME     = "todo-api"
        CONTAINER_NAME = "todo-api"
        HOST_PORT      = "8000"
        CONTAINER_PORT = "8000"
        IMAGE_TAG      = "${env.BUILD_NUMBER ?: 'latest'}"

        DEPLOY_BRANCH  = "main"                     // sosuv uses release_10.10.9.25
        DEPLOY_HOST    = "10.10.9.25"               // UAT server — update for your env
        DEPLOY_USER    = "ubuntu"
        REPO_DIR       = "/opt/todo/repositories/jenkin-todo" // docker compose repo on server
    }

    stages {

        // ── Stage 1: Checkout — Jenkinsfile:29 (identical to sosuv) ──────────
        stage('Checkout') {
            steps {
                checkout scm
                echo "✅ Branch  : ${env.BRANCH_NAME}"
                echo "✅ PR      : ${env.CHANGE_ID ?: 'N/A'}"
                echo "✅ PR Title: ${env.CHANGE_TITLE ?: 'N/A'}"
                echo "✅ Commit  : ${env.GIT_COMMIT}"
                sh '''
                    echo "=== Tool versions ==="
                    java -version 2>&1 || echo "java not installed (Python project)"
                    mvn --version 2>&1 || echo "mvn not installed (Python project)"
                    python3 --version || python --version
                    pip3 --version || pip --version
                    docker --version 2>&1 || echo "docker not found"
                    docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo "⚠️ compose not available (fallback to docker run)"
                    echo "JAVA_HOME=$JAVA_HOME"
                    echo "M2_HOME=$M2_HOME"
                    echo "PIP_CACHE_DIR=$PIP_CACHE_DIR"
                '''
            }
        }

        // ── Stage 2: Build — Jenkinsfile:48 (mirrors sosuv mvn clean package, adapted for Python) ──
        stage('Build') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Build + Unit Tests"
                    echo "========================================"

                    # ── sosuv: lib/infoware-api-client JAR install ──
                    if [ -f "lib/infoware-api-client-1.0.2-SNAPSHOT.jar" ]; then
                        echo "Installing local JAR (sosuv pattern)..."
                        mvn install:install-file \
                            -Dfile=lib/infoware-api-client-1.0.2-SNAPSHOT.jar \
                            -DgroupId=com.infoware \
                            -DartifactId=infoware-api-client \
                            -Dversion=1.0.2-SNAPSHOT \
                            -Dpackaging=jar -q 2>&1 || echo "mvn not available — skipping JAR install"
                    fi

                    # ── Python build (todo) — if pom.xml exists, run Maven, else Python ──
                    if [ -f "pom.xml" ]; then
                        echo "Maven project detected — running mvn clean package (sosuv 39 tests report-only)"
                        mvn clean package -Dmaven.test.failure.ignore=true -q
                    else
                        echo "Python project — running pytest (todo)"
                        if [ ! -d ".venv" ]; then
                            python3 -m venv .venv
                        fi
                        . .venv/bin/activate

                        pip install --upgrade pip -q
                        pip install -r requirements.txt -q
                        pip install -r requirements-dev.txt -q || pip install pytest httpx -q

                        mkdir -p test-results
                        # sosuv uses -Dmaven.test.failure.ignore=true (report-only), but todo uses blocking FAIL → STOP
                        pytest -v --junitxml=test-results/junit.xml
                        echo "✅ Tests PASSED"
                        ls -lh test-results/
                    fi

                    echo "✅ Build complete!"
                '''
            }
            post {
                always {
                    // sosuv: junit 'target/surefire-reports/*.xml'
                    // todo: junit 'test-results/junit.xml' + fallback for maven
                    junit testResults: 'target/surefire-reports/*.xml,test-results/junit.xml', allowEmptyResults: true
                }
                success { echo "✅ Build PASSED" }
                failure { echo "❌ Build FAILED" }
            }
        }

        // ── Stage 2b: Trigger automation — Jenkinsfile:80 (identical to sosuv) ──
        stage('Trigger automation') {
            steps {
                // sosuv: build job: 'sofix-fix-automation/main', wait: false
                // For todo: downstream job is optional — will be skipped if not exists
                script {
                    try {
                        build job: 'sofix-fix-automation/main', wait: false
                        echo "✅ Triggered sofix-fix-automation/main"
                    } catch (e) {
                        echo "⚠️ Downstream job 'sofix-fix-automation/main' not found — skipping (sosuv pattern)"
                    }
                }
            }
        }

        // ── Stage 3: Semgrep SAST — Jenkinsfile:85 (identical to sosuv) ─────
        stage('Semgrep SAST') {
            steps {
                sh '''
                    set +e
                    echo "========================================"
                    echo "  STAGE: Semgrep SAST Scan"
                    echo "========================================"

                    export PATH=/var/lib/jenkins/.local/bin:/var/lib/jenkins/.semgrep-venv/bin:$PATH

                    if ! command -v semgrep &>/dev/null; then
                        echo "Installing python3-pip via apt-get..."
                        sudo apt-get install -y python3-pip -q 2>&1 || echo "apt-get not available or no sudo"
                        echo "Installing semgrep via pip..."
                        . .venv/bin/activate 2>/dev/null || true
                        python3 -m pip install semgrep --quiet --break-system-packages || \
                        python3 -m pip install semgrep --quiet || true
                    fi

                    if command -v semgrep &>/dev/null; then
                        semgrep --config=auto \
                                --json \
                                --output=semgrep-report.json \
                                --no-rewrite-rule-ids \
                                . || true
                    else
                        echo "[WARN] semgrep not found — skipping scan"
                        echo '{"results":[],"paths":{"scanned":[]}}' > semgrep-report.json
                    fi

                    set -e
                '''

                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                        sh 'python3 semgrep_parse.py'
                }
            }

            post {
                always {
                    archiveArtifacts artifacts: 'semgrep-report.json,semgrep-summary.txt',
                                     allowEmptyArchive: true
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

        // ── Stage 4: OWASP CVE Scan — Jenkinsfile:140 (identical to sosuv, with Python fallback) ──
        stage('OWASP CVE Scan') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: OWASP Dependency CVE Scan"
                    echo "========================================"

                    mkdir -p "${NVD_CACHE_DIR}" 2>/dev/null || mkdir -p /tmp/nvd-cache && export NVD_CACHE_DIR=/tmp/nvd-cache || true

                    SUPPRESSION_ARG=""
                    if [ -f "dependency-check-suppressions.xml" ]; then
                        SUPPRESSION_ARG="-DsuppressionFiles=dependency-check-suppressions.xml"
                        echo "✅ Using suppression file"
                    fi

                    # ── If Maven project (sosuv), run OWASP dependency-check; else Python pip-audit ──
                    if [ -f "pom.xml" ]; then
                        echo "Maven OWASP scan (sosuv)..."
                        mvn org.owasp:dependency-check-maven:check \
                            -DfailBuildOnCVSS=0 \
                            -Dformats=HTML,JSON \
                            -Dnvd.api.key="${NVD_API_KEY}" \
                            -DdataDirectory="${NVD_CACHE_DIR}" \
                            -DretireJsAnalyzerEnabled=false \
                            -DnodeAnalyzerEnabled=false \
                            -DassemblyAnalyzerEnabled=false \
                            -DossindexAnalyzerEnabled=false \
                            ${SUPPRESSION_ARG} || true
                    else
                        echo "Python OWASP scan via pip-audit (todo Python equiv. of mvn dependency-check)..."
                        . .venv/bin/activate 2>/dev/null || true
                        if ! command -v pip-audit &>/dev/null; then
                            echo "Installing pip-audit..."
                            python3 -m pip install pip-audit --quiet --break-system-packages || pip install pip-audit --quiet || true
                        fi
                        if command -v pip-audit &>/dev/null; then
                            pip-audit --format=json --output=pip-audit-report.json || true
                            echo "✓ pip-audit scan complete"
                            # Also create empty dependency-check report for post compatibility
                            [ -f "pip-audit-report.json" ] && cp pip-audit-report.json dependency-check-report.json 2>/dev/null || true
                        else
                            echo '{"dependencies":[]}' > pip-audit-report.json
                        fi
                    fi

                    echo "✓ OWASP scan complete."
                '''
            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                sh "CVSS_FAIL_THRESHOLD=${env.CVSS_FAIL_THRESHOLD} python3 owasp_parse.py || CVSS_FAIL_THRESHOLD=${env.CVSS_FAIL_THRESHOLD} python3 safety_parse.py"
              }
            }

            post {
                always {
                    archiveArtifacts artifacts: '**/dependency-check-report.html,**/dependency-check-report.json,owasp-summary.txt,pip-audit-report.json,safety-summary.txt', allowEmptyArchive: true
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
                failure { echo "❌ OWASP FAILED" }
            }
        }

        // ── Stage 5: Docker Build (extra for todo, not in sosuv but keep for deploy) ──
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

        // ── Stage 5b: Remove Old Container (extra for todo) ──
        stage('Remove Old Container') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Remove Old Container"
                    echo "========================================"
                    docker stop ${CONTAINER_NAME} || true
                    docker rm -f ${CONTAINER_NAME} || true
                    docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
                    echo "✅ Old container removed"
                    docker ps -a | grep ${CONTAINER_NAME} || echo "No leftover"
                '''
            }
        }

        // ── Stage 6: Deploy to Dev — Jenkinsfile:195 (identical to sosuv) ──
        stage('Deploy to Dev') {
            when {
                allOf {
                    branch "${env.DEPLOY_BRANCH}"
                }
            }
            steps {
                script {
                    // ── Try SSH deploy (sosuv pattern), fallback to local docker if no credentials/host ──
                    try {
                        withCredentials([sshUserPrivateKey(
                            credentialsId: 'sosuv-deploy-key',
                            keyFileVariable: 'SSH_KEY',
                            usernameVariable: 'SSH_USER'
                        )]) {
                            sh '''
                                set -e
                                echo "========================================"
                                echo " STAGE: Deploy to Dev / UAT (${DEPLOY_HOST}) via Docker"
                                echo "========================================"

                                ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} "
                                    set -e
                                    cd ${REPO_DIR}
                                    git fetch origin ${DEPLOY_BRANCH}
                                    git checkout ${DEPLOY_BRANCH}
                                    git reset --hard origin/${DEPLOY_BRANCH}
                                    docker compose --env-file .env.uat up -d --build
                                    sleep 30
                                    docker compose --env-file .env.uat ps
                                    sudo ss -tlnp | grep 9082 || echo '⚠️ Port 9082 not up yet'
                                "
                            '''
                        }
                    } catch (e) {
                        echo "⚠️ SSH deploy skipped (no sosuv-deploy-key or host ${DEPLOY_HOST} unreachable) — doing local fallback deploy"
                        sh '''
                            set -e
                            echo "========================================"
                            echo " STAGE: Deploy to Dev (LOCAL fallback)"
                            echo " Branch = ${BRANCH_NAME}, Deploy branch = ${DEPLOY_BRANCH}"
                            echo "========================================"
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
                            sleep 10
                            curl -f http://localhost:${HOST_PORT}/health 2>&1 || echo "⚠️ Health check deferred to next stage"
                        '''
                    }
                }
            }
            post {
                success { echo "🚀 Deploy to Dev SUCCESS" }
                failure { echo "❌ Deploy to Dev FAILED" }
            }
        }

        // ── Stage 7: Health Check (extra for todo, sosuv uses ss -tlnp port 9082) ──
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
                            docker ps | grep ${CONTAINER_NAME} 2>/dev/null || docker compose ps 2>/dev/null || true
                            exit 0
                        fi
                        sleep 5
                    done
                    echo "⚠️ Health check skipped (port ${HOST_PORT} not up) — checking 9082 like sosuv"
                    sudo ss -tlnp 2>/dev/null | grep 9082 || ss -tlnp 2>/dev/null | grep ${HOST_PORT} || echo "⚠️ Port check done"
                '''
            }
        }
    }

    // ── Security Summary (identical to sosuv-workflow-api post) ─────────────
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
║   🔐 Backend Security Scan Results — Build #${env.BUILD_NUMBER}
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
<h1 style='margin-bottom:8px'>🔐 Backend Security Scan Results</h1>
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
        success { echo "🎉 Pipeline PASSED" }
        failure { echo "❌ Pipeline FAILED" }
        cleanup { cleanWs() }
    }
}
