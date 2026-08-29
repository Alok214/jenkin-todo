pipeline {
    agent any

    environment {
        IMAGE_NAME     = "todo-api"
        CONTAINER_NAME = "todo-api"
        HOST_PORT      = "8000"
        CONTAINER_PORT = "8000"
        IMAGE_TAG      = "${env.BUILD_NUMBER ?: 'latest'}"
    }

    stages {

        // ── 1. GitHub → Checkout ──────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
                echo "✅ Checked out branch: ${env.BRANCH_NAME ?: 'main'} | Commit: ${env.GIT_COMMIT ?: 'latest'}"
                sh '''
                    echo "=== Tool versions ==="
                    python3 --version || python --version
                    pip3 --version || pip --version
                    docker --version
                    docker compose version || docker-compose --version
                '''
            }
        }

        // ── 2. Run pytest → ❌ STOP on failure ───────────
        stage('Test') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Run pytest (FAIL = STOP)"
                    echo "========================================"

                    # Create venv if not exists
                    if [ ! -d ".venv" ]; then
                        python3 -m venv .venv
                    fi
                    . .venv/bin/activate

                    pip install --upgrade pip -q
                    pip install -r requirements.txt -q
                    pip install -r requirements-dev.txt -q || pip install pytest httpx -q

                    # ❌ Critical: NO "|| true" — failure stops pipeline
                    pytest -v --junitxml=test-results/junit.xml

                    echo "✅ All tests PASSED — proceeding to build"
                '''
            }
            post {
                always {
                    junit testResults: 'test-results/junit.xml', allowEmptyResults: true
                }
                failure {
                    echo "❌ Test failure → STOP (pipeline aborted, no build/deploy)"
                }
            }
        }

        // ── 3. Docker Build ───────────────────────────────
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
                    echo "✅ Docker build complete: ${IMAGE_NAME}:${IMAGE_TAG}"
                '''
            }
        }

        // ── 4. Remove Old Container ───────────────────────
        stage('Remove Old Container') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Remove Old Container"
                    echo "========================================"
                    # stop & remove if exists, ignore if not
                    docker stop ${CONTAINER_NAME} || true
                    docker rm -f ${CONTAINER_NAME} || true
                    # also prune via compose if used before
                    docker compose down || docker-compose down || true
                    echo "✅ Old container removed (or none existed)"
                    docker ps -a | grep ${CONTAINER_NAME} || echo "No leftover container"
                '''
            }
        }

        // ── 5. Deploy New Container ───────────────────────
        stage('Deploy New Container') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Deploy New Container"
                    echo "========================================"
                    # Prefer compose, fallback to docker run
                    if [ -f "docker-compose.yml" ]; then
                        IMAGE_TAG=${IMAGE_TAG} HOST_PORT=${HOST_PORT} docker compose up -d --build
                        docker compose ps
                    else
                        docker run -d --name ${CONTAINER_NAME} -p ${HOST_PORT}:${CONTAINER_PORT} --restart unless-stopped ${IMAGE_NAME}:latest
                        docker ps | grep ${CONTAINER_NAME}
                    fi
                    echo "✅ Deploy done"
                '''
            }
        }

        // ── 6. Health Check → SUCCESS ─────────────────────
        stage('Health Check') {
            steps {
                sh '''
                    set -e
                    echo "========================================"
                    echo " STAGE: Health Check"
                    echo "========================================"
                    echo "Waiting 10s for app to start..."
                    sleep 10

                    # Retry loop (max 30s)
                    for i in 1 2 3 4 5 6; do
                        echo "Attempt $i: curl http://localhost:${HOST_PORT}/health"
                        if curl -f --silent http://localhost:${HOST_PORT}/health; then
                            echo ""
                            echo "✅ Health check PASSED"
                            curl -s http://localhost:${HOST_PORT}/health
                            echo ""
                            docker ps | grep ${CONTAINER_NAME} || docker compose ps || true
                            exit 0
                        fi
                        echo "⏳ Not ready, retry in 5s..."
                        sleep 5
                    done

                    echo "❌ Health check FAILED after 6 attempts"
                    echo "=== Container logs ==="
                    docker logs ${CONTAINER_NAME} || docker compose logs --tail=100 || true
                    exit 1
                '''
            }
        }
    }

    post {
        success {
            echo "🎉 SUCCESS — GitHub → Checkout → Tests → Build → Deploy → Health Check PASSED"
            echo "🚀 App running at http://localhost:${HOST_PORT}"
        }
        failure {
            echo "❌ Pipeline FAILED — check stage above (Test failure stops before build)"
        }
        always {
            archiveArtifacts artifacts: 'test-results/junit.xml', allowEmptyArchive: true
            cleanWs()
        }
    }
}
