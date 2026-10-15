# 北宋官员公服 RPG 装备系统美术与生图规范（权威全案）

> **归属工程**：《宋祚》官员立绘系统重构（RPG 装备部件化）  
> **权威实现**：`sz/game/content/ministers/costumes.py`  
> **核心目的**：将固定立绘重构为类似 RPG 的 6 大装备槽位体系，按官品换装，大幅改善视觉丰富度与历史代入收集感。  
> **历史基准**：北宋元丰改制（1080）后的宋代正统公服/常服制度，杜绝任何时代错位伪宋风。

---

## 一、 RPG 装备槽位架构（6 大装备部件）

| 槽位编号 | 槽位名称 | 宋代正名 | 历史形制与视觉特征 | 品级差异演变 |
|---|---|---|---|---|
| **Slot 1** | **头部（Head）** | **展脚漆纱幞头** | 竹篾/铁线为骨，黑细纱蒙裱，后山前倾，平直展脚横向水平延伸 | **低品**：短窄平脚（长约一尺半）<br>**中品**：平展长脚（长两尺余）<br>**高品**：极展长直铁线角（长两尺半至三尺，平直如弦） |
| **Slot 2** | **身躯（Torso）** | **圆领大袖襕袍** | 纯色无纹素面罗，宽袖（袖阔三尺），下摆横襕（一道横缝拼接），内衬白绢护领 | **低品（七至九品）**：碧绿/豆绿单色素罗<br>**中品（五至六品）**：朱红/绯色纯素绛罗<br>**高品（一至四品）**：深绛紫/紫罗（天子特赐） |
| **Slot 3** | **腰间（Waist）** | **革带与带銙** | 黑熟皮/鹿皮革带，环排十三至十九枚方圆带銙（带板），垂下小铊尾 | **低品**：乌角/青铜素銙<br>**中品**：雕花白银带銙（隐起花银带）<br>**高品**：金荔枝带銙 / 羊脂白玉带板（顶级朝臣） |
| **Slot 4** | **佩饰（Accessory）** | **随身鱼袋** | 革带右侧所悬皮匣囊，内置鱼符（唐宋符契遗制），宋制五品以上方得佩鱼 | **低品**：空缺（七品以下无佩鱼荣典）<br>**中品**：银鱼袋（底缀白银锁扣与银鱼符）<br>**高品**：金鱼袋（紫袍金鱼，纯金錾花囊与金鱼符） |
| **Slot 5** | **手持（Held）** | **朝笏（手板）** | 官员上朝端奉于胸前的记事长板，两手持捧，平头微弧 | **低品**：槐木/厚竹削制质朴木笏<br>**中品**：青润象牙朝笏（交趾真象牙）<br>**高品**：透润老象牙玉笏（牙质通透，温润如脂） |
| **Slot 6** | **足部（Feet）** | **靴履（履）** | 黑熟皮六缝平头靴，薄底黑革，轻便肃整 | **低品**：熟牛皮薄底乌皮靴<br>**中品**：熟羊皮软里六缝乌皮靴<br>**高品**：精熟鹿皮乌缎靴（薄黑底） |

---

## 二、 严格历史禁令（Strict Taboo List）

为彻底清除影视剧与市面游戏常见之清宫戏、明代戏混淆元素，生图提示词与美术资产严格执行以下禁忌审查：

> [!CAUTION]
> 1. **严禁胸前补子（Mandarin Square）**：补子是明清两代官服的核心特征，北宋公服通体**纯色素面，绝无胸前方形动物刺绣**！
> 2. **严禁龙纹与团龙（Dragon Embroidery）**：宋代官员绝不可能身着带龙纹的袍服，哪怕宰相宗亲亦不可。
> 3. **严禁明清官帽与顶戴**：严禁出现清代花翎红缨顶戴、明代圆顶折角乌纱帽（软翅或下垂翅）。
> 4. **严禁厚白戏曲靴底**：京剧厚底官靴（白高底）系明清戏曲产物，宋代靴子为薄黑皮底。

---

## 三、 各品级完整服饰配置与生图提示词（AI Prompts）

### 3.1 低品公服（七至九品 · 绿袍）
- **代表官职**：知县、县丞、通判、主簿、签判、选人、监当官
- **装备组合**：短展脚漆纱幞头 + 碧绿素面圆领襕袍 + 黑角铜銙革带 + 无鱼袋 + 槐木质朴笏 + 薄底乌皮六缝靴

#### 中文提示词（Prompt CN）
```text
北宋院体工笔设色绢本肖像。一位北宋低品公服官员，半身立像。身穿草绿单色素罗圆领大袖襕袍，下摆横襕，纯素无纹，绝无补子与龙纹；头戴短展脚漆纱幞头，黑细纱蒙裱，两侧展脚短窄微平；腰束黑熟皮革带，排缀质朴乌角与青铜带板，无鱼袋；双手端奉槐木平直木笏于胸前；通体纯色素雅，古朴赭黄绢本底色，宋画严谨写实气韵，大师级线条。
```

#### 英文生图提示词（Midjourney / FLUX Prompt EN）
```text
Traditional Chinese Northern Song Dynasty court portrait, gongbi painting on aged antique raw silk canvas. A half-length portrait of a Song Dynasty civil official wearing an authentic plain solid pea-green round-collar robe (lanpao), wide sleeves, pure monochrome fabric with strictly NO chest patches, NO buzi, NO dragon embroidery. Wearing a formal Song lacquered futou hat with stiff straight thin horizontal flat wings. Fastened around waist is an authentic black leather belt with plain dark horn plaques, no fish pouch. Both hands hold a slender wooden hu tablet in front of chest. Museum artifact quality, historical realism, masterwork brushwork --ar 3:4 --style raw --v 6.1
```

---

### 3.2 中品公服（五至六品 · 绯袍）
- **代表官职**：知府、知州、侍郎、给事中、员外郎、都进奏院提辖、登闻鼓院判官
- **装备组合**：平展硬脚黑漆幞头 + 朱红纯素圆领襕袍 + 隐花银銙黑革带 + 白银鱼袋（银鱼符） + 青润微直象牙朝笏 + 熟羊皮平底乌皮靴

#### 中文提示词（Prompt CN）
```text
北宋院体工笔设色绢本肖像。一位北宋中品五六品公服官员，半身立像。身穿正红绛红精织素面罗圆领大袖襕袍，通体纯色，无任何方块补子或刺绣；头戴铁线平展长脚黑漆幞头，长两尺余，水平平直刚挺；腰束黑鹿皮革带，排缀十三枚起雀花白银带銙，革带右侧垂悬白银鱼袋；双手端奉青润交趾象牙朝笏；古朴赭黄绢本底色，端庄肃穆，宋代宫廷院体画风。
```

#### 英文生图提示词（Midjourney / FLUX Prompt EN）
```text
Traditional Chinese Northern Song Dynasty court portrait, gongbi painting on aged antique raw silk canvas. A half-length portrait of a Song Dynasty civil official wearing an authentic plain solid scarlet-crimson round-collar robe (lanpao), wide sleeves, pure monochrome fabric with strictly NO chest patches, NO buzi, NO dragon embroidery. Wearing a formal Song lacquered futou hat with long perfectly horizontal flat stiff wings. Fastened around waist is an authentic leather belt with chased sterling silver plaques, accompanied by a silver fish pouch (yudai) hanging on waist. Both hands hold an off-white ivory hu tablet in front of chest. Museum artifact quality, historical realism, masterwork brushwork --ar 3:4 --style raw --v 6.1
```

---

### 3.3 高品公服（一至四品 · 紫袍金鱼）
- **代表官职**：宰相、执政、枢密使、尚书、知枢密院事、御史中丞、开封府尹、节度使
- **装备组合**：极展长直角黑纱幞头 + 深绛紫特织素面襕袍 + 荔枝金带 / 羊脂白玉带 + 鎏金金鱼袋 + 透润老象牙玉笏 + 精熟鹿皮乌缎靴

#### 中文提示词（Prompt CN）
```text
北宋院体工笔设色绢本肖像。一位北宋宰执重臣高品公服官员，半身立像。身穿深邃绛紫特织素面罗圆领大袖襕袍，通体纯紫无杂饰，低调奢华；头戴熟铜铁线精撑极展长直平脚黑纱幞头，长近三尺，极平极展，尽显一品威仪；腰束红皮革带，排缀透雕纯金荔枝带銙，右肋悬挂镂空鎏金金鱼袋（紫袍金鱼）；双手肃穆端捧透润老象牙白玉笏；赭黄古绢底色，重臣威仪，气度端凝。
```

#### 英文生图提示词（Midjourney / FLUX Prompt EN）
```text
Traditional Chinese Northern Song Dynasty court portrait, gongbi painting on aged antique raw silk canvas. A half-length portrait of a Song Dynasty senior prime minister wearing an authentic plain solid deep purple-violet round-collar robe (lanpao), wide sleeves, pure monochrome fabric with strictly NO chest patches, NO buzi, NO dragon embroidery. Wearing a formal Song lacquered futou hat with extremely long horizontal flat stiff wings stretching wide. Fastened around waist is an authentic crimson belt with carved pure gold plaques, accompanied by a golden fish pouch (yudai) hanging on waist. Both hands hold a gently curved exquisite white ivory tablet in front of chest. Museum artifact quality, historical realism, masterwork brushwork --ar 3:4 --style raw --v 6.1
```

---

### 3.4 通用负面提示词（Universal Negative Prompt）
```text
buzi, mandarin square, embroidered chest patch, chest emblem, dragon robe, dragon embroidery, golden dragon, qilin, Ming dynasty hat, Qing dynasty hat, official hat with tassels, official hat with peacock feather, curved wing hat, white thick boot soles, modern hanfu, fantasy, blurry, low quality, deformed hands, extra fingers
```

---

## 四、 分层立绘管线集成（Layer Compositing）

生图产物进入管线后，按 `PORTRAIT_PIPELINE.md` 标准进行分层：
1. **官服层裁剪**：尺寸统一为 `810×1080`（3:4），背景绢底 `#C4A877`；
2. **头部层抠取**：头部层扣除原官服，下方羽化渐变至透明；
3. **动态合成调用**：
   ```python
   from content.ministers.data import get_portrait_path, get_minister_equipment
   
   # 获取立绘（官阶变化时自动切换服色 body_{pose}_{tier}.png）
   portrait_file = get_portrait_path("曾布", rank="正一品")
   
   # 获取 RPG 装备槽位数据
   equip = get_minister_equipment("曾布")
   # equip['slots']['robe'] -> 深绛紫特织素面襕袍
   # equip['slots']['fish_pouch'] -> 鎏金金鱼袋
   ```
