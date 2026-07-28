# Live2D 数字人项目问题解决方案文档

## 一、问题定位

当前项目结构：

    React 前端
        |
        |-- Agent
        |-- FastAPI
        |-- TTS
        |-- LipSync
        |
        ↓
    Live2D模型

经过检查：

-   mao_pro.model3.json 正常
-   texture_00.png 正常
-   AudioManager 正常
-   TTS流程正常

最终问题定位：

> 自定义 CubismRenderer.ts 实现不完整，无法正确渲染官方 Live2D Cubism
> 模型。

表现：

-   模型碎片化
-   身体部件错位
-   透明区域异常
-   头发、衣服显示错误

------------------------------------------------------------------------

# 二、问题原因

## 1. Cubism版本不匹配

当前模型：

    mao_pro.model3.json

属于：

    Cubism 3/4 模型格式

但是当前 Renderer：

    Cubism 6 WebGL renderer

存在兼容风险。

------------------------------------------------------------------------

## 2. 自写Renderer缺少核心功能

当前Renderer实现：

    读取drawable
    ↓
    创建WebGL Buffer
    ↓
    绘制mesh

但是Live2D官方Renderer还包含：

-   Clipping Manager
-   Mask Buffer
-   Stencil处理
-   DrawOrder排序
-   Blend模式管理
-   Shader管理

缺少这些会导致：

    模型数据
     ↓
    错误绘制
     ↓
    部件碎裂

------------------------------------------------------------------------

# 三、推荐解决方案

## 使用官方 Live2D Cubism SDK for Web

不要继续维护自己的：

    CubismRenderer.ts

替换为：

    Live2D Cubism SDK Renderer

------------------------------------------------------------------------

# 四、项目改造方案

## 保留部分

以下代码无需修改：

    AudioManager.ts

    useVoice.ts

    FastAPI

    Agent

    TTS

这些负责：

-   语音
-   AI回复
-   数据传输

------------------------------------------------------------------------

## 替换部分

删除：

    src/live2d/CubismRenderer.ts

改用：

    Live2D Cubism SDK Web Renderer

------------------------------------------------------------------------

# 五、新项目结构

    frontend

    src

     ├── live2d

     │    ├── CubismManager.ts
     │    ├── Live2DModel.ts
     │    └── LipSync.ts


    public

     └── live2d

          └── mao_pro

               ├── mao_pro.model3.json
               ├── mao_pro.moc3
               ├── textures
               ├── motions
               └── physics

------------------------------------------------------------------------

# 六、口型同步修改

当前模型：

    LipSync

    ParamA

只有一个嘴型参数。

不要使用：

    ParamA
    ParamI
    ParamU
    ParamE
    ParamO

修改为：

    ParamA

控制：

    嘴巴开合程度

即可。

------------------------------------------------------------------------

# 七、实施步骤

## Step 1

下载：

    Live2D Cubism SDK for Web

获取：

    live2dcubismcore.min.js

    Framework

------------------------------------------------------------------------

## Step 2

引入SDK：

    index.html

    加载 live2dcubismcore.min.js

------------------------------------------------------------------------

## Step 3

创建：

    CubismManager.ts

负责：

-   初始化CubismFramework
-   加载model3.json
-   创建模型实例

------------------------------------------------------------------------

## Step 4

替换Renderer

原：

    Custom WebGL Renderer

改：

    CubismRenderer_WebGL

------------------------------------------------------------------------

## Step 5

重新接入口型

流程：

    TTS

    ↓

    viseme

    ↓

    ParamA

    ↓

    Live2D嘴部动画

------------------------------------------------------------------------

# 八、最终架构

                     用户

                      |

                  React页面

                      |

              LangChain Agent

                      |

                  FastAPI

                      |

            ----------------

            TTS       LLM

             |
             |
          音频数据

             |
          viseme数据

                      |

              Live2D Cubism SDK

                      |

                  mao_pro模型

------------------------------------------------------------------------

# 九、最终效果目标

完成后：

✅ 模型完整显示

✅ 纹理正常

✅ 物理效果正常

✅ 动作正常

✅ 表情正常

✅ TTS播放正常

✅ 口型同步正常

------------------------------------------------------------------------

# 十、开发建议

数字人项目中：

不要自己实现Live2D底层渲染。

推荐：

    Live2D SDK
    负责身体

    Agent
    负责思考

    TTS
    负责声音

    LipSync
    负责同步

这样开发效率最高。
