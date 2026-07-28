# Live2D Cubism Web 白色矩形渲染问题修复方案

## 一、项目背景

本项目是 React + TypeScript 的 AI 数字人系统。

技术栈： - React - TypeScript - Vite - Live2D Cubism SDK for Web -
FastAPI - TTS - LipSync

模型：

    mao_pro.model3.json

来源： Live2D 官方 Sample。

------------------------------------------------------------------------

## 二、当前状态

已经从自定义 WebGL Renderer 切换到官方：

    CubismRenderer_WebGL

架构：

    React
     |
    Live2DCanvas
     |
    CubismManager
     |
    CubismUserModel
     |
    CubismRenderer_WebGL
     |
    Live2D模型

------------------------------------------------------------------------

## 三、问题表现

模型主体已经正常：

-   身体正常
-   衣服正常
-   头发正常
-   动作正常

但是出现：

    白色矩形区域

特点：

-   不是模型损坏
-   不是 texture 丢失
-   怀疑 Mask / Clipping / Alpha 渲染异常

------------------------------------------------------------------------

## 四、问题定位

重点检查：

    WebGL Texture
    Alpha
    Blend
    Shader

原因：

当前虽然使用官方 Renderer，但是 Texture 和 WebGL
初始化仍可能存在自定义配置，导致：

    官方Renderer
    +
    错误WebGL状态
    +
    Alpha不匹配

    ↓

    Mask异常

    ↓

    白色矩形

------------------------------------------------------------------------

## 五、修复方案

### 1. 删除 Mipmap

检查：

``` ts
gl.generateMipmap(gl.TEXTURE_2D)
```

如果存在，删除。

不要使用：

``` ts
gl.LINEAR_MIPMAP_LINEAR
```

改：

``` ts
gl.texParameteri(
 gl.TEXTURE_2D,
 gl.TEXTURE_MIN_FILTER,
 gl.LINEAR
);
```

------------------------------------------------------------------------

### 2. 检查 WebGL Alpha

推荐：

``` ts
canvas.getContext(
"webgl2",
{
 alpha:true,
 premultipliedAlpha:false,
 antialias:true,
 stencil:true
}
)
```

重点：

-   stencil 支持 Mask
-   alpha 保持透明
-   避免 Alpha 冲突

------------------------------------------------------------------------

### 3. 检查 Blend

普通 Alpha：

``` ts
gl.blendFunc(
 gl.SRC_ALPHA,
 gl.ONE_MINUS_SRC_ALPHA
)
```

预乘 Alpha：

``` ts
gl.blendFunc(
 gl.ONE,
 gl.ONE_MINUS_SRC_ALPHA
)
```

必须保证：

Texture Alpha 类型

和

Blend模式

一致。

------------------------------------------------------------------------

### 4. 检查 Shader

确认：

    public/shaders/WebGL/

使用官方 Cubism Shader。

不要混用：

-   旧 Renderer shader
-   自定义 shader

------------------------------------------------------------------------

## 六、修改原则

不要：

-   修改模型
-   重新导出模型
-   修改 texture
-   替换 Live2D 框架

保持：

    CubismRenderer_WebGL

------------------------------------------------------------------------

## 七、最终目标

修复后：

-   mao_pro 完整显示
-   Mask 正常
-   Clipping 正常
-   表情正常
-   Motion 正常
-   TTS LipSync 正常

最终架构：

    AI Agent
     |
    FastAPI
     |
    TTS
     |
    LipSync
     |
    Live2D Cubism SDK
     |
    mao_pro模型

------------------------------------------------------------------------

## 八、给 AI 编程助手的任务

请 AI：

1.  分析 Live2D 初始化代码
2.  找出具体错误位置
3.  修改 WebGL 配置
4.  修复 Texture 处理
5.  修复 Alpha / Blend 问题
6.  保持官方 CubismRenderer_WebGL

不要：

-   换 PixiJS
-   回退自定义 Renderer
-   重新制作模型
