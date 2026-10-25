# Supabase 傻瓜式配置教程

目标：让账号、密码哈希和每位同学的单词保存在 Supabase PostgreSQL 中，而 ECDICT 词典仍从项目里的 SQLite 只读查询。

![Supabase 配置流程](docs/supabase-setup-flow.svg)

## 第一步：注册 Supabase

1. 打开 [Supabase 官网](https://supabase.com/)。
2. 点击右上角 `Start your project`。
3. 使用邮箱、GitHub 或 Google 完成注册。
4. 登录后进入 `Dashboard`。

免费版足够小范围同学使用，但平台额度以后可能调整。

## 第二步：创建项目

1. 点击 `New project`。
2. `Project name` 填写 `wordbook`。
3. `Database Password` 设置一个强密码并立即保存。
4. `Region` 选择离你和同学较近的区域，例如 `Southeast Asia (Singapore)`。
5. 点击 `Create new project`，等待数据库初始化完成。

这里的数据库密码不是同学使用的登录密码。同学登录的是生词本自己的用户名和密码。

## 第三步：打开 SQL Editor

在 Supabase 左侧导航栏点击：

```text
SQL Editor
```

点击 `New query` 或编辑器中的 `+`，把下面的 SQL 完整粘贴进去，然后点击 `Run`。

```sql
create table if not exists public.app_users (
    username text primary key
        check (
            username = lower(username)
            and username ~ '^[a-z0-9_-]{3,20}$'
        ),
    password_hash text not null
        check (length(password_hash) >= 50),
    created_at timestamptz not null default now()
);

create table if not exists public.wordbook_entries (
    username text not null
        references public.app_users(username)
        on delete cascade,
    word text not null,
    normalized text not null,
    created_at timestamptz not null default now(),
    primary key (username, normalized)
);

create index if not exists wordbook_entries_user_idx
    on public.wordbook_entries (username);

alter table public.app_users enable row level security;
alter table public.wordbook_entries enable row level security;

revoke all on table public.app_users from anon, authenticated;
revoke all on table public.wordbook_entries from anon, authenticated;
```

建表结果：

| 表名 | 字段 | 用途 |
|---|---|---|
| `app_users` | `username` | 唯一用户名 |
| `app_users` | `password_hash` | bcrypt 密码哈希，不保存明文密码 |
| `app_users` | `created_at` | 注册时间 |
| `wordbook_entries` | `username` | 生词属于哪个同学 |
| `wordbook_entries` | `word` | 单词原始拼写 |
| `wordbook_entries` | `normalized` | 小写标准形式，用于去重 |
| `wordbook_entries` | `created_at` | 收藏时间 |

`PRIMARY KEY (username, normalized)` 表示同一位同学不能重复收藏同一个单词，但不同同学可以收藏同一个单词。

最后的 `REVOKE` 和 RLS 设置会阻止匿名前端直接读取账号表。Streamlit 服务通过服务端数据库连接访问；数据库连接串只能放进 `secrets.toml`。

## 第四步：确认表已经创建

在左侧点击 `Table Editor`，应能看到：

```text
app_users
wordbook_entries
```

也可以回到 `SQL Editor` 运行：

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('app_users', 'wordbook_entries');
```

应返回两行。

## 第五步：复制 PostgreSQL 连接串

在 Supabase Dashboard 点击项目顶部的 `Connect`。如果没有看到，进入：

```text
Project Settings → Database → Connection string → URI
```

选择 `Session pooler` 或 `URI`，复制类似下面的字符串：

```text
postgresql://postgres.project-ref:YOUR_PASSWORD@aws-0-region.pooler.supabase.com:5432/postgres
```

把 `YOUR_PASSWORD` 替换为第二步保存的数据库密码。通常再确认末尾包含：

```text
?sslmode=require
```

不要把这个字符串发到聊天或提交到 GitHub。它拥有数据库访问权限。

## 第六步：生成 Cookie 密钥

在 PowerShell 中运行：

```powershell
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 32
$rng.GetBytes($bytes)
$rng.Dispose()
[Convert]::ToBase64String($bytes)
```

复制输出，填入下一步的 `cookie_key`。这个值用于给登录 Cookie 签名。

## 第七步：创建 secrets.toml

复制模板：

```powershell
Copy-Item .\.streamlit\secrets.toml.example .\.streamlit\secrets.toml
```

使用文本编辑器填写：

```toml
[authenticator]
cookie_name = "wordbook_auth"
cookie_key = "这里填写上一步生成的随机字符串"
cookie_expiry_days = 30
registration_code = "自己设置一个班级邀请码"

[database]
url = "这里填写完整的 PostgreSQL 连接串"
```

`.streamlit/secrets.toml` 已在 `.gitignore` 中忽略，不会被正常提交。

## 第八步：启动并验证

```powershell
cd E:\生词本
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

打开：

```text
http://localhost:8501
```

验证顺序：

1. 在“注册新账号”页签填写用户名、密码和邀请码。
2. 点击“注册”。
3. 切换到“登录”页签登录。
4. 搜索 `apple` 并点击“加入生词本”。
5. 在 Supabase `Table Editor → wordbook_entries` 中应看到：

   - `username` 是你的用户名。
   - `word` 是 `apple`。
   - `normalized` 是 `apple`。

注册第二位同学后，分别查询生词本，应只能看到自己的单词。

## 部署到 Streamlit Community Cloud

1. 把代码提交并推送到 GitHub。
2. 在 Streamlit Community Cloud 创建 App。
3. 在 App 的 `Settings → Secrets` 中粘贴与本地 `secrets.toml` 相同的内容。
4. 部署后得到类似 `https://wordbook-your-name.streamlit.app` 的网址。

云端不需要 Microsoft Entra，也不需要 OIDC 回调地址。

## 常见错误

### `password authentication failed`

连接串中的数据库密码不正确。重新复制 Supabase 的连接串，不要使用同学登录密码。

### `relation "app_users" does not exist`

第三步 SQL 没有成功执行。回到 `SQL Editor`，重新运行完整 SQL。

### `duplicate key value violates unique constraint`

用户名已经被注册。换一个用户名；数据库唯一约束会阻止重复账号。

### 页面显示“云端尚未配置 Supabase 数据库”

部署后没有在 Secrets 中填写 `[database] url`。

### 页面显示“尚未配置登录 Cookie”

缺少 `[authenticator] cookie_name` 或 `cookie_key`。

### 能登录，但看不到刚添加的单词

检查：

1. 是否用同一个用户名登录。
2. Supabase 表中是否有对应记录。
3. 数据库连接串是否指向正确项目。

### 部署后应用重启，数据丢失

检查是否使用了 Supabase PostgreSQL。SQLite 只适合本机测试，不适合 Streamlit Cloud 的持久数据。
