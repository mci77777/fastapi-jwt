# 数据库设计文档

## 📋 概述

本文档定义GymBro管理后台的数据库schema，基于RBAC（基于角色的访问控制）模型设计。

## 🗄️ 数据库信息

- **数据库类型**：PostgreSQL 15+
- **ORM框架**：SQLAlchemy 2.0（异步）
- **迁移工具**：Alembic
- **字符集**：UTF-8
- **时区**：UTC

## 📊 ER图

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    users    │───────│ user_roles  │───────│    roles    │
└─────────────┘       └─────────────┘       └─────────────┘
                                                    │
                                                    │
                                            ┌───────┴───────┐
                                            │               │
                                      ┌─────▼─────┐   ┌────▼──────┐
                                      │role_menus │   │ role_apis │
                                      └─────┬─────┘   └────┬──────┘
                                            │              │
                                      ┌─────▼─────┐   ┌────▼──────┐
                                      │   menus   │   │   apis    │
                                      └───────────┘   └───────────┘

┌─────────────┐
│ audit_logs  │
└─────────────┘
```

## 📋 表结构定义

### 1. users（用户表）

存储系统用户的基本信息。

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500),
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);
```

**字段说明**：

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | UUID | 用户唯一标识 | 主键 |
| username | VARCHAR(50) | 用户名 | 唯一，非空 |
| email | VARCHAR(100) | 邮箱 | 唯一，非空 |
| password_hash | VARCHAR(255) | 密码哈希（bcrypt） | 非空 |
| avatar_url | VARCHAR(500) | 头像URL | 可空 |
| phone | VARCHAR(20) | 手机号 | 可空 |
| is_active | BOOLEAN | 是否激活 | 默认TRUE |
| is_superuser | BOOLEAN | 是否超级管理员 | 默认FALSE |
| last_login_at | TIMESTAMP | 最后登录时间 | 可空 |
| created_at | TIMESTAMP | 创建时间 | 默认当前时间 |
| updated_at | TIMESTAMP | 更新时间 | 默认当前时间 |

### 2. roles（角色表）

定义系统角色。

```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_roles_code ON roles(code);
CREATE INDEX idx_roles_is_active ON roles(is_active);
```

**字段说明**：

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | UUID | 角色唯一标识 | 主键 |
| name | VARCHAR(50) | 角色名称 | 唯一，非空 |
| code | VARCHAR(50) | 角色代码（如admin, user） | 唯一，非空 |
| description | TEXT | 角色描述 | 可空 |
| is_active | BOOLEAN | 是否激活 | 默认TRUE |
| created_at | TIMESTAMP | 创建时间 | 默认当前时间 |
| updated_at | TIMESTAMP | 更新时间 | 默认当前时间 |

### 3. user_roles（用户-角色关联表）

多对多关系：一个用户可以有多个角色，一个角色可以分配给多个用户。

```sql
CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_user_roles_role_id ON user_roles(role_id);
```

### 4. menus（菜单表）

存储系统菜单/路由信息，支持树形结构。

```sql
CREATE TABLE menus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL,
    title VARCHAR(100) NOT NULL,
    path VARCHAR(200),
    component VARCHAR(200),
    icon VARCHAR(50),
    parent_id UUID REFERENCES menus(id) ON DELETE CASCADE,
    order_num INTEGER DEFAULT 0,
    is_visible BOOLEAN DEFAULT TRUE,
    is_external BOOLEAN DEFAULT FALSE,
    redirect VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_menus_parent_id ON menus(parent_id);
CREATE INDEX idx_menus_order_num ON menus(order_num);
CREATE INDEX idx_menus_is_visible ON menus(is_visible);
```

**字段说明**：

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | UUID | 菜单唯一标识 | 主键 |
| name | VARCHAR(50) | 菜单名称（路由name） | 非空 |
| title | VARCHAR(100) | 菜单标题（显示名称） | 非空 |
| path | VARCHAR(200) | 路由路径 | 可空 |
| component | VARCHAR(200) | 组件路径 | 可空 |
| icon | VARCHAR(50) | 图标名称 | 可空 |
| parent_id | UUID | 父菜单ID | 可空，外键 |
| order_num | INTEGER | 排序号 | 默认0 |
| is_visible | BOOLEAN | 是否可见 | 默认TRUE |
| is_external | BOOLEAN | 是否外部链接 | 默认FALSE |
| redirect | VARCHAR(200) | 重定向路径 | 可空 |
| created_at | TIMESTAMP | 创建时间 | 默认当前时间 |
| updated_at | TIMESTAMP | 更新时间 | 默认当前时间 |

### 5. role_menus（角色-菜单关联表）

多对多关系：一个角色可以访问多个菜单，一个菜单可以分配给多个角色。

```sql
CREATE TABLE role_menus (
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    menu_id UUID REFERENCES menus(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (role_id, menu_id)
);

CREATE INDEX idx_role_menus_role_id ON role_menus(role_id);
CREATE INDEX idx_role_menus_menu_id ON role_menus(menu_id);
```

### 6. apis（API端点表）

存储系统API端点信息，用于API级权限控制。

```sql
CREATE TABLE apis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    description TEXT,
    module VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (path, method)
);

CREATE INDEX idx_apis_module ON apis(module);
CREATE INDEX idx_apis_is_active ON apis(is_active);
```

**字段说明**：

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | UUID | API唯一标识 | 主键 |
| path | VARCHAR(200) | API路径（如/api/v1/user） | 非空 |
| method | VARCHAR(10) | HTTP方法（GET/POST/PUT/DELETE） | 非空 |
| description | TEXT | API描述 | 可空 |
| module | VARCHAR(50) | 所属模块 | 可空 |
| is_active | BOOLEAN | 是否激活 | 默认TRUE |
| created_at | TIMESTAMP | 创建时间 | 默认当前时间 |
| updated_at | TIMESTAMP | 更新时间 | 默认当前时间 |

**唯一约束**：(path, method) - 同一路径和方法的组合唯一

### 7. role_apis（角色-API关联表）

多对多关系：一个角色可以访问多个API，一个API可以分配给多个角色。

```sql
CREATE TABLE role_apis (
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    api_id UUID REFERENCES apis(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (role_id, api_id)
);

CREATE INDEX idx_role_apis_role_id ON role_apis(role_id);
CREATE INDEX idx_role_apis_api_id ON role_apis(api_id);
```

### 8. audit_logs（审计日志表）

记录系统操作日志。

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
```

**字段说明**：

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | UUID | 日志唯一标识 | 主键 |
| user_id | UUID | 用户ID | 可空，外键 |
| username | VARCHAR(50) | 用户名（冗余存储） | 可空 |
| action | VARCHAR(50) | 操作类型（CREATE/UPDATE/DELETE） | 非空 |
| resource | VARCHAR(100) | 资源类型（user/role/menu） | 非空 |
| resource_id | VARCHAR(100) | 资源ID | 可空 |
| details | JSONB | 操作详情（JSON格式） | 可空 |
| ip_address | VARCHAR(45) | IP地址（支持IPv6） | 可空 |
| user_agent | TEXT | 用户代理 | 可空 |
| status | VARCHAR(20) | 操作状态（success/failed） | 可空 |
| created_at | TIMESTAMP | 创建时间 | 默认当前时间 |

## 🔧 初始数据

### 默认角色

```sql
INSERT INTO roles (name, code, description) VALUES
('超级管理员', 'admin', '拥有所有权限'),
('普通用户', 'user', '基础权限');
```

### 默认用户

```sql
INSERT INTO users (username, email, password_hash, is_superuser) VALUES
('admin', 'admin@gymbro.com', '$2b$12$...', TRUE);

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE u.username = 'admin' AND r.code = 'admin';
```

## 📈 性能优化建议

1. **索引优化**：
   - 为常用查询字段添加索引
   - 复合索引用于多字段查询
   - 定期分析索引使用情况

2. **分区策略**：
   - audit_logs表按月分区
   - 历史数据归档

3. **查询优化**：
   - 使用JOIN代替子查询
   - 避免SELECT *
   - 使用EXPLAIN分析查询计划

## 🔒 安全建议

1. **密码存储**：使用bcrypt哈希，成本因子12
2. **敏感数据**：考虑加密存储（如手机号）
3. **审计日志**：保留至少6个月
4. **备份策略**：每日全量备份，每小时增量备份

---

**文档版本**：v1.0
**最后更新**：2025-09-30

