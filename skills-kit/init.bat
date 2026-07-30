@echo off
REM ============================================================
REM skills-kit 安装脚本 (Windows)
REM 用法:
REM   init.bat C:\path\to\project
REM   init.bat --update C:\path\to\project
REM   init.bat --self
REM ============================================================
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "UPDATE=false"

if "%~1"=="--update" (
    set "UPDATE=true"
    set "TARGET=%~f2"
) else if "%~1"=="--self" (
    for %%I in ("%SCRIPT_DIR%..") do set "TARGET=%%~fI"
) else (
    set "TARGET=%~f1"
)

echo skills-kit init → %TARGET%
if "%UPDATE%"=="true" (echo mode: update) else (echo mode: install)

REM ── 1. 复制 skills 目录 ────────────────────────────────
echo [1/3] 复制 skills/ ...
if exist "%TARGET%\skills" rmdir /s /q "%TARGET%\skills"
xcopy /e /i /q "%SCRIPT_DIR%skills" "%TARGET%\skills" > nul
echo        skills/ → %TARGET%\skills\

REM ── 2. 复制 CORE_RULES.md ──────────────────────────────
echo [2/3] 复制 CORE_RULES.md ...
copy /y "%SCRIPT_DIR%CORE_RULES.md" "%TARGET%\skills\CORE_RULES.md" > nul
echo        CORE_RULES.md → %TARGET%\skills\CORE_RULES.md

REM ── 3. 合并 CLAUDE.md ─────────────────────────────────
echo [3/3] 合并 CLAUDE.md ...

if exist "%TARGET%\CLAUDE.md" (
    echo        目标项目已有 CLAUDE.md

    REM 检查是否已有硬约束块
    findstr /c:"## 硬约束" "%TARGET%\CLAUDE.md" > nul 2>&1
    if errorlevel 1 (
        echo        追加硬约束块...
        echo. >> "%TARGET%\CLAUDE.md"
        echo ## 硬约束（始终生效，不需要关键词触发）>> "%TARGET%\CLAUDE.md"
        echo. >> "%TARGET%\CLAUDE.md"
        echo 以下规则每次对话自动执行，不可跳过：>> "%TARGET%\CLAUDE.md"
        echo. >> "%TARGET%\CLAUDE.md"
        echo 1. 声称过关前先跑验证 -- 说"没问题了"之前必须先执行 CI 全部命令看到 ALL PASS>> "%TARGET%\CLAUDE.md"
        echo 2. 修改前先读文件 -- 改任何文件前先 Read 目标文件确认当前内容>> "%TARGET%\CLAUDE.md"
        echo 3. 批量操作后必须验证 -- 批量替换后必须 Read 回文件内容确认>> "%TARGET%\CLAUDE.md"
        echo 4. 违规直接承认 -- 违反准则直接承认，不辩解，修完写教训>> "%TARGET%\CLAUDE.md"
        echo 5. 先读后写 -- 写代码前先确认数据源真实结构，不凭文档臆测>> "%TARGET%\CLAUDE.md"
        echo 6. 不凭猜测 -- 不用"应该是""默认值是0"代替实际读取>> "%TARGET%\CLAUDE.md"
        echo 7. 防御性输出 -- LLM输出进入下游前必须经过过滤管道>> "%TARGET%\CLAUDE.md"
        echo 8. 依赖方向正确 -- 上层依赖下层，无循环依赖>> "%TARGET%\CLAUDE.md"
        echo 9. 匹配 skill -- 复杂/高风险任务主动搜索匹配 skill 文件>> "%TARGET%\CLAUDE.md"
        echo. >> "%TARGET%\CLAUDE.md"
    )

    REM 追加 SKILLS 索引
    findstr /c:"## 可用 Skills" "%TARGET%\CLAUDE.md" > nul 2>&1
    if errorlevel 1 (
        echo        追加 Skills 索引...
        echo. >> "%TARGET%\CLAUDE.md"
        echo ## 可用 Skills>> "%TARGET%\CLAUDE.md"
        echo. >> "%TARGET%\CLAUDE.md"
        echo ^| Skill ^| 描述 ^| 触发关键词 ^|>> "%TARGET%\CLAUDE.md"
        echo ^|-------^|------^|----------^|>> "%TARGET%\CLAUDE.md"
        echo ^| verify ^| 提交前全量 CI 验证 ^| "提交"/"push"/"没问题了" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| read-before-code ^| 编码前强制读取数据源 ^| "对接SDK"/"数据格式"/"配置文件" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| tdd ^| 测试驱动开发 ^| "写测试"/"test"/"TDD" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| diagnose-bugs ^| 结构化 bug 诊断 ^| "bug"/"不工作"/"报错"/"排查" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| code-review ^| 代码审查（规范+实现） ^| "审查"/"review"/"看看代码" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| codebase-design ^| 模块设计 ^| "设计模块"/"接口设计"/"模块化" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| defensive-output ^| LLM输出防护 ^| "过滤"/"清洗"/"TTS" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| prototype-first ^| 原型先行 ^| "页面布局"/"画原型"/"UI设计" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| implement ^| 按依赖方向实现 ^| "开始写代码"/"按方案做"/"实现" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| grill-me ^| 方案追问 ^| "分析一下"/"这个方案"/"怎么设计" ^|>> "%TARGET%\CLAUDE.md"
        echo ^| handoff ^| 会话交接 ^| "总结一下"/"交接"/"存档" ^|>> "%TARGET%\CLAUDE.md"
        echo. >> "%TARGET%\CLAUDE.md"
    )
) else (
    echo        目标项目无 CLAUDE.md，从模板创建
    copy /y "%SCRIPT_DIR%CLAUDE.md" "%TARGET%\CLAUDE.md" > nul
    echo        CLAUDE.md 已创建
)

echo.
echo =========================================
echo  skills-kit 安装完成
echo =========================================
echo.
echo 已安装到: %TARGET%
echo   - %TARGET%\skills\         # skill 文件
echo   - %TARGET%\CORE_RULES.md   # 行为准则
echo   - %TARGET%\CLAUDE.md       # 硬约束已合并
echo.
echo 下次对话开始时 CLAUDE.md 中的硬约束即自动生效。
