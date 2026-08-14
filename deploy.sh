#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CONTAINER_NAME="geo-audit-service"
export COMPOSE_PROJECT_NAME="site-geo"

if ! command -v docker >/dev/null 2>&1; then
    echo "错误：未安装 Docker。"
    exit 1
fi

if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose -f compose.yaml)
    DEPLOY_MODE="compose"
    echo ">>> 使用 Docker Compose v2"
elif command -v docker-compose >/dev/null 2>&1; then
    # Compose v1 (1.29.x) cannot reliably recreate images produced by newer
    # Docker versions and may fail with KeyError: 'ContainerConfig'.
    DEPLOY_MODE="docker"
    echo ">>> 检测到旧版 Docker Compose v1，使用纯 Docker 兼容模式"
else
    DEPLOY_MODE="docker"
    echo ">>> 未安装 Docker Compose，使用纯 Docker 兼容模式"
fi

if [ ! -f ".env" ]; then
    echo "错误：缺少 ${SCRIPT_DIR}/.env。"
    echo "请先执行：cp .env.example .env，并填写数据库及 API 密钥。"
    exit 1
fi

echo ">>> 1/5 拉取最新代码"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git pull --ff-only
else
    echo "当前目录不是 Git 仓库，跳过 git pull。"
fi

echo ">>> 2/5 校验 Compose 配置"
if [ "${DEPLOY_MODE}" = "compose" ]; then
    "${COMPOSE[@]}" config --quiet
else
    echo "纯 Docker 模式无需校验 Compose。"
fi

echo ">>> 3/5 检查旧容器"
if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
    if [ "${DEPLOY_MODE}" = "compose" ]; then
        COMPOSE_PROJECT="$(
            docker container inspect \
              --format '{{ index .Config.Labels "com.docker.compose.project" }}' \
              "${CONTAINER_NAME}" 2>/dev/null || true
        )"
    else
        COMPOSE_PROJECT=""
    fi
    if [ "${COMPOSE_PROJECT}" != "${COMPOSE_PROJECT_NAME}" ]; then
        echo "移除旧容器，随后用统一配置重建。"
        docker container rm --force "${CONTAINER_NAME}"
    fi
fi

echo ">>> 4/5 重建镜像并启动容器"
if [ "${DEPLOY_MODE}" = "compose" ]; then
    "${COMPOSE[@]}" build --pull
    "${COMPOSE[@]}" up \
        --detach \
        --force-recreate \
        --remove-orphans
else
    docker build --pull --tag geo-audit-service:latest .
    if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
        docker container rm --force "${CONTAINER_NAME}"
    fi
    docker run \
        --detach \
        --name "${CONTAINER_NAME}" \
        --publish 8023:8023 \
        --env-file .env \
        --env ALLOW_PLAYWRIGHT=true \
        --volume "${SCRIPT_DIR}/app:/app/app" \
        --restart unless-stopped \
        --health-cmd "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8023/health', timeout=5)\"" \
        --health-interval 15s \
        --health-timeout 6s \
        --health-retries 5 \
        --health-start-period 20s \
        geo-audit-service:latest \
        uvicorn app.main:app --host 0.0.0.0 --port 8023 --reload
fi

show_status() {
    if [ "${DEPLOY_MODE}" = "compose" ]; then
        "${COMPOSE[@]}" ps
    else
        docker container ps --filter "name=^/${CONTAINER_NAME}$"
    fi
}

show_logs() {
    if [ "${DEPLOY_MODE}" = "compose" ]; then
        "${COMPOSE[@]}" logs --tail 100 "${CONTAINER_NAME}"
    else
        docker container logs --tail 100 "${CONTAINER_NAME}"
    fi
}

echo ">>> 5/5 等待健康检查"
for attempt in $(seq 1 18); do
    HEALTH="$(
        docker container inspect \
          --format '{{ if .State.Health }}{{ .State.Health.Status }}{{ else }}unknown{{ end }}' \
          "${CONTAINER_NAME}" 2>/dev/null || true
    )"
    case "${HEALTH}" in
        healthy)
            echo "部署完成：http://127.0.0.1:8023"
            show_status
            exit 0
            ;;
        unhealthy)
            echo "容器健康检查失败，最近日志如下："
            show_logs
            exit 1
            ;;
        *)
            printf '等待容器启动（%s/18，状态：%s）...\n' "${attempt}" "${HEALTH:-starting}"
            sleep 5
            ;;
    esac
done

echo "等待健康检查超时，最近日志如下："
show_logs
exit 1
