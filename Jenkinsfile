// Declarative Jenkins pipeline mirroring .github/workflows/ci.yml + build-deploy.yml
//
// Assumes a Jenkins agent labelled `linux-docker` that has:
//   - python3.11
//   - docker + docker buildx
//   - access to a container registry (configured via DOCKER_REGISTRY env)
//
// Credentials used:
//   - registry-creds:    Username/password for $DOCKER_REGISTRY (Jenkins credentials ID)
//   - github-token:      For optional GitHub status updates
//
// Equivalent capabilities to the GitHub Actions workflows so the project can run
// in TCS-style Jenkins-only environments without losing the test/build story.

pipeline {
  agent { label 'linux-docker' }

  options {
    timestamps()
    timeout(time: 45, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '20'))
    disableConcurrentBuilds(abortPrevious: true)
  }

  environment {
    PYTHON       = 'python3.11'
    VENV         = '.venv'
    IMAGE_NAME   = 'credit-default-api'
    SHORT_SHA    = sh(returnStdout: true, script: "git rev-parse --short HEAD").trim()
    REGISTRY     = "${env.DOCKER_REGISTRY ?: 'docker.io/jayaram9196'}"
  }

  stages {

    stage('setup') {
      steps {
        sh '''
          $PYTHON -m venv $VENV
          . $VENV/bin/activate
          pip install --upgrade pip
          pip install -e ".[serving,monitoring,dev]"
        '''
      }
    }

    stage('lint') {
      parallel {
        stage('ruff')   { steps { sh '. $VENV/bin/activate && ruff check src tests' } }
        stage('black')  { steps { sh '. $VENV/bin/activate && black --check src tests' } }
        stage('mypy')   { steps { sh '. $VENV/bin/activate && mypy src' } }
        stage('bandit') { steps { sh '. $VENV/bin/activate && bandit -r src -ll' } }
      }
    }

    stage('unit tests') {
      steps {
        sh '. $VENV/bin/activate && pytest tests/unit -v --cov=src --cov-report=xml --junitxml=junit-unit.xml'
      }
      post {
        always {
          junit 'junit-unit.xml'
          archiveArtifacts artifacts: 'coverage.xml', allowEmptyArchive: true
        }
      }
    }

    stage('smoke pipeline') {
      steps {
        sh '''
          . $VENV/bin/activate
          $PYTHON - <<'PY'
          import yaml, pathlib
          p = pathlib.Path('params.yaml')
          d = yaml.safe_load(p.read_text())
          d['model_training']['optuna_trials'] = 2
          d['model_training']['cv_folds'] = 3
          d['model_evaluation']['max_demographic_parity_diff'] = 0.5
          d['model_evaluation']['max_equal_opportunity_diff'] = 0.5
          p.write_text(yaml.safe_dump(d))
          PY
          $PYTHON -m src.data.ingest
          $PYTHON -m src.data.validate
          $PYTHON -m src.features.build
          $PYTHON -m src.models.train
          $PYTHON -m src.models.evaluate
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: 'reports/**/*, models/*.joblib', allowEmptyArchive: true
        }
      }
    }

    stage('integration tests') {
      steps {
        sh '. $VENV/bin/activate && pytest tests/integration -v --junitxml=junit-integration.xml'
      }
      post { always { junit 'junit-integration.xml' } }
    }

    stage('docker build + push') {
      when { branch 'main' }
      steps {
        withCredentials([usernamePassword(credentialsId: 'registry-creds',
                                          usernameVariable: 'REG_USER',
                                          passwordVariable: 'REG_PASS')]) {
          sh '''
            echo "$REG_PASS" | docker login $REGISTRY -u "$REG_USER" --password-stdin
            docker buildx build \
              --file docker/Dockerfile.api \
              --tag $REGISTRY/$IMAGE_NAME:$SHORT_SHA \
              --tag $REGISTRY/$IMAGE_NAME:latest \
              --push \
              .
          '''
        }
      }
    }

    stage('trivy image scan') {
      when { branch 'main' }
      steps {
        sh '''
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:latest image \
            --severity CRITICAL,HIGH \
            --ignore-unfixed \
            --exit-code 0 \
            $REGISTRY/$IMAGE_NAME:$SHORT_SHA
        '''
      }
    }
  }

  post {
    success { echo "Pipeline complete for ${env.SHORT_SHA}" }
    failure { echo "Pipeline failed; check artifacts above." }
    always  { cleanWs() }
  }
}
