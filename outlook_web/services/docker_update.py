"""Docker API 自更新服务

通过 Docker API 实现容器自更新功能，作为 Watchtower 的替代方案。

安全要求：
- 默认关闭，需 DOCKER_SELF_UPDATE_ALLOW=true 启用
- 检测 docker.sock 是否可访问
- 校验镜像名白名单（仅允许 guangshanshui/outlook-email-plus）
- 操作前记录审计日志

回滚机制：
- 拉取新镜像前保存旧 digest
- 创建新容器但不立即删除旧容器
- 新容器 healthcheck 通过后才删除旧容器
- 失败时保留旧容器
"""

import os
import logging
import time
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 允许自动更新的镜像白名单
ALLOWED_IMAGE_PREFIXES = [
    "guangshanshui/outlook-email-plus",
    "outlook-email-plus",  # 兼容本地构建
]


def is_docker_api_enabled() -> bool:
    """检查是否启用 Docker API 自更新功能"""
    return os.getenv("DOCKER_SELF_UPDATE_ALLOW", "false").lower() == "true"


def check_docker_socket() -> Tuple[bool, str]:
    """检查 docker.sock 是否可访问

    Returns:
        (is_available, message)
    """
    socket_path = "/var/run/docker.sock"

    if not os.path.exists(socket_path):
        return False, f"Docker socket 不存在: {socket_path}"

    if not os.access(socket_path, os.R_OK | os.W_OK):
        return False, f"Docker socket 无读写权限: {socket_path}"

    # 尝试连接 Docker API
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return True, "Docker socket 可用"
    except ImportError:
        return False, "缺少 docker 库，请运行: pip install docker"
    except Exception as e:
        return False, f"无法连接 Docker API: {str(e)}"


def validate_image_name(image_name: str) -> Tuple[bool, str]:
    """验证镜像名是否在白名单内

    Args:
        image_name: 镜像名（如 guangshanshui/outlook-email-plus:latest）

    Returns:
        (is_valid, message)
    """
    # 去除 tag 部分进行检查
    base_image = image_name.split(":")[0]

    for allowed_prefix in ALLOWED_IMAGE_PREFIXES:
        if base_image == allowed_prefix or base_image.startswith(allowed_prefix + "/"):
            return True, "镜像名校验通过"

    return False, f"镜像名不在白名单内: {image_name}"


def get_current_container_info() -> Optional[Dict[str, Any]]:
    """获取当前容器信息

    Returns:
        {
            "id": "abc123...",
            "name": "outlook-email-plus",
            "image": "guangshanshui/outlook-email-plus:latest",
            "image_id": "sha256:...",
            "labels": {...},
            "env": {...},
            "volumes": {...},
            "networks": {...},
            "restart_policy": {...}
        }
    """
    try:
        import docker

        client = docker.from_env()

        # 通过环境变量 HOSTNAME 获取当前容器 ID
        hostname = os.getenv("HOSTNAME", "")
        if not hostname:
            logger.error("无法获取容器 ID (HOSTNAME 为空)")
            return None

        # Docker 容器的 HOSTNAME 通常是容器 ID 的短格式
        # 尝试通过短 ID 查找容器
        try:
            container = client.containers.get(hostname)
        except docker.errors.NotFound:
            # 如果短 ID 找不到，尝试通过名称查找
            containers = client.containers.list(filters={"name": "outlook-email-plus"})
            if not containers:
                logger.error(f"未找到容器: {hostname}")
                return None
            container = containers[0]

        # 提取容器配置信息
        inspect_data = container.attrs
        config = inspect_data.get("Config", {})
        host_config = inspect_data.get("HostConfig", {})
        network_settings = inspect_data.get("NetworkSettings", {})

        return {
            "id": container.id,
            "short_id": container.short_id,
            "name": container.name,
            "image": config.get("Image", ""),
            "image_id": inspect_data.get("Image", ""),
            "labels": config.get("Labels", {}),
            "env": config.get("Env", []),
            "volumes": host_config.get("Binds", []),
            "networks": list(network_settings.get("Networks", {}).keys()),
            "restart_policy": host_config.get("RestartPolicy", {}),
            "ports": host_config.get("PortBindings", {}),
            "working_dir": config.get("WorkingDir", ""),
            "user": config.get("User", ""),
        }

    except Exception as e:
        logger.error(f"获取当前容器信息失败: {str(e)}", exc_info=True)
        return None


def pull_latest_image(image_name: str) -> Tuple[bool, str, Optional[str]]:
    """拉取最新镜像

    Args:
        image_name: 镜像名（如 guangshanshui/outlook-email-plus:latest）

    Returns:
        (success, message, new_digest)
    """
    try:
        import docker

        client = docker.from_env()

        logger.info(f"开始拉取镜像: {image_name}")

        # 拉取镜像（可能耗时较长）
        image = client.images.pull(image_name)

        # 获取新镜像的 digest
        new_digest = image.id

        logger.info(f"镜像拉取成功: {image_name}, digest: {new_digest}")

        return True, "镜像拉取成功", new_digest

    except Exception as e:
        error_msg = f"拉取镜像失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg, None


def compare_image_digest(current_digest: str, new_digest: str) -> bool:
    """比较镜像 digest 是否相同

    Returns:
        True: 镜像相同（已是最新）
        False: 镜像不同（需要更新）
    """
    return current_digest == new_digest


def create_new_container(
    old_container_info: Dict[str, Any],
    new_image: str,
) -> Tuple[bool, str, Optional[Any]]:
    """创建新容器（复制旧容器配置）

    Args:
        old_container_info: 旧容器信息
        new_image: 新镜像名

    Returns:
        (success, message, new_container)
    """
    try:
        import docker

        client = docker.from_env()

        # 生成新容器名称
        old_name = old_container_info["name"]
        new_name = f"{old_name}_new_{int(time.time())}"

        # 构建容器创建参数
        create_kwargs = {
            "image": new_image,
            "name": new_name,
            "detach": True,
            "labels": old_container_info.get("labels", {}),
            "environment": old_container_info.get("env", []),
            "volumes": _parse_volumes(old_container_info.get("volumes", [])),
            "network": None,  # 创建后单独连接网络
            "restart_policy": old_container_info.get("restart_policy", {}),
            "ports": _parse_ports(old_container_info.get("ports", {})),
            "working_dir": old_container_info.get("working_dir", ""),
            "user": old_container_info.get("user", ""),
        }

        logger.info(f"创建新容器: {new_name}")
        logger.debug(f"容器创建参数: {create_kwargs}")

        # 创建容器（但不启动）
        new_container = client.containers.create(**create_kwargs)

        # 连接到相同的网络
        for network_name in old_container_info.get("networks", []):
            try:
                network = client.networks.get(network_name)
                network.connect(new_container)
                logger.info(f"容器已连接到网络: {network_name}")
            except Exception as e:
                logger.warning(f"连接网络失败 {network_name}: {str(e)}")

        logger.info(f"新容器创建成功: {new_container.short_id}")

        return True, "新容器创建成功", new_container

    except Exception as e:
        error_msg = f"创建新容器失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg, None


def _parse_volumes(volumes: list) -> Dict[str, Dict[str, str]]:
    """解析 volumes 配置

    Args:
        volumes: ["/host/path:/container/path:rw", ...]

    Returns:
        {"/host/path": {"bind": "/container/path", "mode": "rw"}}
    """
    result = {}

    for volume in volumes:
        parts = volume.split(":")
        if len(parts) >= 2:
            host_path = parts[0]
            container_path = parts[1]
            mode = parts[2] if len(parts) >= 3 else "rw"

            result[host_path] = {
                "bind": container_path,
                "mode": mode,
            }

    return result


def _parse_ports(ports: Dict[str, Any]) -> Dict[str, Any]:
    """解析 ports 配置

    Args:
        ports: {"5050/tcp": [{"HostPort": "5050"}]}

    Returns:
        {"5050/tcp": 5050}
    """
    result = {}

    for container_port, bindings in ports.items():
        if bindings and isinstance(bindings, list) and len(bindings) > 0:
            host_port = bindings[0].get("HostPort")
            if host_port:
                result[container_port] = int(host_port)

    return result


def start_new_container(container: Any) -> Tuple[bool, str]:
    """启动新容器

    Args:
        container: Docker container 对象

    Returns:
        (success, message)
    """
    try:
        logger.info(f"启动新容器: {container.short_id}")

        container.start()

        # 等待容器启动（最多 10 秒）
        for i in range(10):
            container.reload()
            if container.status == "running":
                logger.info(f"新容器已启动: {container.short_id}")
                return True, "新容器启动成功"
            time.sleep(1)

        return False, "新容器启动超时"

    except Exception as e:
        error_msg = f"启动新容器失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def health_check_new_container(container: Any, timeout: int = 30) -> Tuple[bool, str]:
    """健康检查新容器

    Args:
        container: Docker container 对象
        timeout: 超时时间（秒）

    Returns:
        (is_healthy, message)
    """
    try:
        logger.info(f"健康检查新容器: {container.short_id}")

        # 简单检查：容器是否在运行
        start_time = time.time()

        while time.time() - start_time < timeout:
            container.reload()

            # 容器状态检查
            if container.status != "running":
                return False, f"容器状态异常: {container.status}"

            # 如果容器有 healthcheck，检查健康状态
            health = container.attrs.get("State", {}).get("Health", {})
            if health:
                health_status = health.get("Status", "")
                if health_status == "healthy":
                    logger.info("新容器健康检查通过")
                    return True, "健康检查通过"
                elif health_status == "unhealthy":
                    return False, "容器健康检查失败"
            else:
                # 没有 healthcheck，等待 5 秒后视为健康
                if time.time() - start_time > 5:
                    logger.info("新容器无 healthcheck 配置，等待 5 秒后视为健康")
                    return True, "健康检查通过（无 healthcheck 配置）"

            time.sleep(2)

        return False, "健康检查超时"

    except Exception as e:
        error_msg = f"健康检查失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def stop_old_container(container_id: str) -> Tuple[bool, str]:
    """停止旧容器

    Args:
        container_id: 容器 ID

    Returns:
        (success, message)
    """
    try:
        import docker

        client = docker.from_env()
        container = client.containers.get(container_id)

        logger.info(f"停止旧容器: {container.short_id}")

        container.stop(timeout=10)

        logger.info(f"旧容器已停止: {container.short_id}")

        return True, "旧容器已停止"

    except Exception as e:
        error_msg = f"停止旧容器失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def rename_containers(old_container_id: str, new_container_id: str) -> Tuple[bool, str]:
    """重命名容器（新容器使用原名称）

    Args:
        old_container_id: 旧容器 ID
        new_container_id: 新容器 ID

    Returns:
        (success, message)
    """
    try:
        import docker

        client = docker.from_env()

        old_container = client.containers.get(old_container_id)
        new_container = client.containers.get(new_container_id)

        old_name = old_container.name
        backup_name = f"{old_name}_backup_{int(time.time())}"

        logger.info(f"重命名旧容器: {old_name} -> {backup_name}")
        old_container.rename(backup_name)

        logger.info(f"重命名新容器: {new_container.name} -> {old_name}")
        new_container.rename(old_name)

        return True, "容器重命名成功"

    except Exception as e:
        error_msg = f"重命名容器失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def cleanup_old_container(container_id: str, remove: bool = False) -> Tuple[bool, str]:
    """清理旧容器

    Args:
        container_id: 容器 ID
        remove: 是否删除容器（默认 False，仅保留备份）

    Returns:
        (success, message)
    """
    try:
        import docker

        client = docker.from_env()
        container = client.containers.get(container_id)

        if remove:
            logger.info(f"删除旧容器: {container.short_id}")
            container.remove(force=True)
            return True, "旧容器已删除"
        else:
            logger.info(f"保留旧容器作为备份: {container.short_id}")
            return True, "旧容器已保留作为备份"

    except Exception as e:
        error_msg = f"清理旧容器失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def self_update(remove_old: bool = False) -> Dict[str, Any]:
    """执行容器自更新

    完整流程：
    1. 安全检查（启用开关、docker.sock 可访问性）
    2. 获取当前容器信息
    3. 验证镜像名白名单
    4. 拉取最新镜像
    5. 比较 digest（相同则跳过）
    6. 创建新容器（复制配置）
    7. 启动新容器
    8. 健康检查
    9. 停止旧容器
    10. 重命名容器
    11. 清理/保留旧容器

    Args:
        remove_old: 是否删除旧容器（默认 False，保留作为备份）

    Returns:
        {
            "success": bool,
            "message": str,
            "steps": [
                {"step": "check_permission", "success": True, "message": "..."},
                ...
            ]
        }
    """
    steps = []

    # Step 1: 安全检查 - 启用开关
    if not is_docker_api_enabled():
        return {
            "success": False,
            "message": "Docker API 自更新功能未启用（需设置 DOCKER_SELF_UPDATE_ALLOW=true）",
            "steps": [
                {
                    "step": "check_permission",
                    "success": False,
                    "message": "Docker API 自更新功能未启用",
                }
            ],
        }

    steps.append(
        {
            "step": "check_permission",
            "success": True,
            "message": "Docker API 自更新功能已启用",
        }
    )

    # Step 2: 安全检查 - docker.sock 可访问性
    socket_ok, socket_msg = check_docker_socket()
    steps.append(
        {
            "step": "check_docker_socket",
            "success": socket_ok,
            "message": socket_msg,
        }
    )

    if not socket_ok:
        return {
            "success": False,
            "message": socket_msg,
            "steps": steps,
        }

    # Step 3: 获取当前容器信息
    current_container = get_current_container_info()
    if not current_container:
        steps.append(
            {
                "step": "get_container_info",
                "success": False,
                "message": "无法获取当前容器信息",
            }
        )
        return {
            "success": False,
            "message": "无法获取当前容器信息",
            "steps": steps,
        }

    steps.append(
        {
            "step": "get_container_info",
            "success": True,
            "message": f"当前容器: {current_container['name']} ({current_container['short_id']})",
        }
    )

    # Step 4: 验证镜像名白名单
    current_image = current_container["image"]
    valid_image, validate_msg = validate_image_name(current_image)
    steps.append(
        {
            "step": "validate_image",
            "success": valid_image,
            "message": validate_msg,
        }
    )

    if not valid_image:
        return {
            "success": False,
            "message": validate_msg,
            "steps": steps,
        }

    # Step 5: 拉取最新镜像
    pull_ok, pull_msg, new_digest = pull_latest_image(current_image)
    steps.append(
        {
            "step": "pull_image",
            "success": pull_ok,
            "message": pull_msg,
        }
    )

    if not pull_ok:
        return {
            "success": False,
            "message": pull_msg,
            "steps": steps,
        }

    # Step 6: 比较 digest
    current_digest = current_container["image_id"]
    is_same = compare_image_digest(current_digest, new_digest)

    if is_same:
        steps.append(
            {
                "step": "compare_digest",
                "success": True,
                "message": "镜像已是最新，无需更新",
            }
        )
        return {
            "success": True,
            "message": "镜像已是最新，无需更新",
            "steps": steps,
        }

    steps.append(
        {
            "step": "compare_digest",
            "success": True,
            "message": f"检测到新版本镜像 (digest 不同)",
        }
    )

    # Step 7: 创建新容器
    create_ok, create_msg, new_container = create_new_container(
        current_container,
        current_image,
    )
    steps.append(
        {
            "step": "create_container",
            "success": create_ok,
            "message": create_msg,
        }
    )

    if not create_ok:
        return {
            "success": False,
            "message": create_msg,
            "steps": steps,
        }

    # Step 8: 启动新容器
    start_ok, start_msg = start_new_container(new_container)
    steps.append(
        {
            "step": "start_container",
            "success": start_ok,
            "message": start_msg,
        }
    )

    if not start_ok:
        # 启动失败，删除新容器
        try:
            new_container.remove(force=True)
            logger.info(f"新容器启动失败，已删除: {new_container.short_id}")
        except Exception as e:
            logger.error(f"删除失败的新容器时出错: {str(e)}")

        return {
            "success": False,
            "message": start_msg,
            "steps": steps,
        }

    # Step 9: 健康检查
    health_ok, health_msg = health_check_new_container(new_container)
    steps.append(
        {
            "step": "health_check",
            "success": health_ok,
            "message": health_msg,
        }
    )

    if not health_ok:
        # 健康检查失败，停止并删除新容器
        try:
            new_container.stop(timeout=5)
            new_container.remove(force=True)
            logger.info(f"新容器健康检查失败，已删除: {new_container.short_id}")
        except Exception as e:
            logger.error(f"删除不健康的新容器时出错: {str(e)}")

        return {
            "success": False,
            "message": health_msg,
            "steps": steps,
        }

    # Step 10: 停止旧容器
    stop_ok, stop_msg = stop_old_container(current_container["id"])
    steps.append(
        {
            "step": "stop_old_container",
            "success": stop_ok,
            "message": stop_msg,
        }
    )

    if not stop_ok:
        logger.warning(f"停止旧容器失败，但新容器已启动: {stop_msg}")

    # Step 11: 重命名容器
    rename_ok, rename_msg = rename_containers(current_container["id"], new_container.id)
    steps.append(
        {
            "step": "rename_containers",
            "success": rename_ok,
            "message": rename_msg,
        }
    )

    if not rename_ok:
        logger.warning(f"重命名容器失败: {rename_msg}")

    # Step 12: 清理旧容器
    cleanup_ok, cleanup_msg = cleanup_old_container(
        current_container["id"], remove=remove_old
    )
    steps.append(
        {
            "step": "cleanup_old_container",
            "success": cleanup_ok,
            "message": cleanup_msg,
        }
    )

    # 返回成功结果
    return {
        "success": True,
        "message": "容器自更新完成",
        "new_container_id": new_container.short_id,
        "old_container_id": current_container["short_id"],
        "steps": steps,
    }
