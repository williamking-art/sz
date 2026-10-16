# -*- coding: utf-8 -*-
"""构建北宋官员召对立绘换装系统方案 B 权威展示台 HTML。"""
import base64
import json
import os

BRAIN_DIR = r"C:\Users\william\.gemini\antigravity\brain\21dc1567-8824-46b3-91a5-6021d8db2a9f"
LAYERS_ROOT = r"sz/game/content/ministers/paperdoll/layers"
OUT_HTML = os.path.join(BRAIN_DIR, "minister_audience_showcase.html")


def to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def build_html():
    print("正在编码图层素材为 base64...")
    assets = {
        "cai_jing": to_b64(os.path.join(BRAIN_DIR, "cai_jing_real_gongbi.png")),
        "zhong_shizhong": to_b64(os.path.join(BRAIN_DIR, "zhong_shizhong_real_gongbi.png")),
        "new_scholar_ouyang": to_b64(os.path.join(BRAIN_DIR, "new_scholar_ouyang_real_gongbi.png")),
        "silk_bg": to_b64(os.path.join(LAYERS_ROOT, "backgrounds", "silk_raw.png")),
        "doll_young": to_b64(os.path.join(LAYERS_ROOT, "dolls", "doll_young.png")),
        "doll_middle": to_b64(os.path.join(LAYERS_ROOT, "dolls", "doll_middle.png")),
        "doll_elder": to_b64(os.path.join(LAYERS_ROOT, "dolls", "doll_elder.png")),
        "robe_zi": to_b64(os.path.join(LAYERS_ROOT, "robes", "robe_zi.png")),
        "robe_fei": to_b64(os.path.join(LAYERS_ROOT, "robes", "robe_fei.png")),
        "robe_lv": to_b64(os.path.join(LAYERS_ROOT, "robes", "robe_lv.png")),
        "futou_long": to_b64(os.path.join(LAYERS_ROOT, "futou", "futou_long.png")),
        "futou_short": to_b64(os.path.join(LAYERS_ROOT, "futou", "futou_short.png")),
        "hu_ivory": to_b64(os.path.join(LAYERS_ROOT, "held", "hu_ivory.png")),
        "hu_wood": to_b64(os.path.join(LAYERS_ROOT, "held", "hu_wood.png")),
        "pouch_gold": to_b64(os.path.join(LAYERS_ROOT, "pouches", "pouch_gold.png")),
        "pouch_silver": to_b64(os.path.join(LAYERS_ROOT, "pouches", "pouch_silver.png")),
    }

    assets_json = json.dumps(assets)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>《宋祚》北宋大臣召对立绘换装系统展示台 (方案 B 权威落地)</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    .song-silk {{
      background-color: #C4A877;
      background-image: radial-gradient(circle at 50% 35%, #D6BD8E 0%, #B89966 100%);
    }}
    /* 缓步官仪呼吸微动动画 */
    @keyframes ministerBreathe {{
      0%, 100% {{ transform: translateY(0px) scale(1); }}
      50% {{ transform: translateY(-4px) scale(1.004); }}
    }}
    /* 铁线长直展角微颤 */
    @keyframes futouTremble {{
      0%, 100% {{ transform: rotate(0deg); }}
      25% {{ transform: rotate(0.18deg); }}
      75% {{ transform: rotate(-0.18deg); }}
    }}
    .anim-breathe {{
      animation: ministerBreathe 4.2s ease-in-out infinite;
      transform-origin: 50% 80%;
    }}
    .anim-futou {{
      animation: futouTremble 3.8s ease-in-out infinite;
      transform-origin: 50% 230px;
    }}
    .layer-transition {{
      transition: opacity 0.3s ease, transform 0.3s ease;
    }}
  </style>
</head>
<body class="bg-stone-900 text-stone-100 min-h-screen p-4 flex flex-col items-center">

  <!-- 顶部主标题 -->
  <header class="w-full max-w-6xl mb-4 border-b border-stone-800 pb-3 flex flex-wrap items-center justify-between gap-2">
    <div>
      <h1 class="text-2xl font-bold tracking-wide flex items-center gap-2">
        <span>📜 《宋祚》大臣召对动态立绘换装系统</span>
        <span class="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium">方案 B：3D 骨架烘焙 2D 工笔图层</span>
      </h1>
      <p class="text-xs text-stone-400 mt-1">
        统一 810×1080 画幅 · 严格骨骼锚点对齐 (Head 405,230 / Collar 405,360 / Waist 680) · 彻底消除断头白洞与重叠双帽
      </p>
    </div>
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-amber-500/10 text-amber-400 text-xs font-semibold border border-amber-500/30">
        <span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span> 纯正院体工笔设色绢本
      </span>
    </div>
  </header>

  <!-- 主内容双栏布局 -->
  <main class="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

    <!-- 左侧：立绘舞台视口 (810x1080 3:4 黄金画幅) -->
    <section class="lg:col-span-6 bg-stone-950/70 rounded-xl border border-stone-800 shadow-2xl p-4 flex flex-col items-center relative">
      <!-- 召对名牌 -->
      <div class="w-full flex justify-between items-center mb-3 px-1">
        <div>
          <span id="lbl_minister_title" class="text-xs font-mono text-amber-500">从一品 尚书左仆射兼门下侍郎</span>
          <h2 id="lbl_minister_name" class="text-2xl font-bold text-stone-100 flex items-center gap-2">
            <span>蔡京</span>
            <span id="lbl_costume_tag" class="text-xs px-2 py-0.5 rounded bg-purple-900/60 text-purple-300 border border-purple-700/50">深绛紫袍 · 金鱼袋</span>
          </h2>
        </div>
        <div id="lbl_emotion_badge" class="px-2.5 py-1 rounded text-xs font-medium bg-stone-800 text-stone-300 border border-stone-700">
          恭谨肃立 (respectful)
        </div>
      </div>

      <!-- 核心舞台视口 (固定 3:4 比例，810x1080 空间) -->
      <div id="portrait_stage" class="w-full max-w-[420px] aspect-[3/4] song-silk rounded-lg border-2 border-stone-700/60 shadow-2xl overflow-hidden relative select-none">
        <!-- Layer 0: 宣和老绢本背景 -->
        <img id="layer_bg" class="absolute inset-0 w-full h-full object-cover z-0 pointer-events-none" src="" alt="绢底" />
        
        <!-- Layer 1: 底模素体 (自带白绢交领中单与发髻) -->
        <img id="layer_doll" class="absolute inset-0 w-full h-full object-contain z-10 pointer-events-none anim-breathe" src="" alt="素体" />
        
        <!-- Layer 5: 大袖圆领官袍 (紫/红/绿) -->
        <img id="layer_robe" class="absolute inset-0 w-full h-full object-contain z-20 pointer-events-none anim-breathe" src="" alt="官服" />
        
        <!-- Layer 7: 佩鱼袋 (金/银) -->
        <img id="layer_pouch" class="absolute inset-0 w-full h-full object-contain z-30 pointer-events-none anim-breathe" src="" alt="鱼袋" />
        
        <!-- Layer 8: 手持朝笏 (象牙/槐木) -->
        <img id="layer_held" class="absolute inset-0 w-full h-full object-contain z-40 pointer-events-none anim-breathe" src="" alt="朝笏" />
        
        <!-- Layer 9: 漆纱幞头 (长直角/短平角) -->
        <img id="layer_futou" class="absolute inset-0 w-full h-full object-contain z-50 pointer-events-none anim-futou" src="" alt="幞头" />
      </div>

      <!-- 骨骼与微动指示器 -->
      <div class="w-full flex justify-between items-center text-xs text-stone-400 mt-3 pt-2 border-t border-stone-800">
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> 官仪呼吸微动 (Spine: 4.2s)
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></span> 铁线展角轻颤 (Head: 3.8s)
        </span>
        <button id="btn_toggle_motion" class="px-2 py-0.5 rounded bg-stone-800 hover:bg-stone-700 text-stone-300 text-xs border border-stone-700 transition">
          暂停动效
        </button>
      </div>
    </section>

    <!-- 右侧：交互换装控制台与召对状态机 -->
    <section class="lg:col-span-6 flex flex-col gap-4">

      <!-- 1. 经典名臣一键召对 -->
      <div class="bg-stone-950/70 rounded-xl border border-stone-800 p-4 shadow-sm">
        <div class="text-xs font-semibold text-amber-500 uppercase tracking-wider mb-2.5 flex items-center justify-between">
          <span>1. 朝堂名臣一键召对 (Presetted Ministers)</span>
          <span class="text-[10px] text-stone-400">方案 B 真实渲染成果</span>
        </div>
        <div class="grid grid-cols-3 gap-2">
          <button onclick="applyPreset('cai_jing')" class="p-2.5 rounded-lg border border-purple-800/60 bg-purple-950/30 hover:bg-purple-900/50 text-left transition flex flex-col gap-1">
            <span class="text-sm font-bold text-purple-200">蔡京 (70岁)</span>
            <span class="text-xs text-stone-400">从一品 · 尚书左仆射</span>
            <span class="text-[10px] text-purple-300 mt-1">紫袍 · 长角 · 金鱼袋 · 象牙笏</span>
          </button>
          <button onclick="applyPreset('zhong_shizhong')" class="p-2.5 rounded-lg border border-red-800/60 bg-red-950/30 hover:bg-red-900/50 text-left transition flex flex-col gap-1">
            <span class="text-sm font-bold text-red-200">种师中 (48岁)</span>
            <span class="text-xs text-stone-400">正四品 · 经略安抚使</span>
            <span class="text-[10px] text-red-300 mt-1">绯袍 · 长角 · 银鱼袋 · 槐木笏</span>
          </button>
          <button onclick="applyPreset('new_scholar_ouyang')" class="p-2.5 rounded-lg border border-emerald-800/60 bg-emerald-950/30 hover:bg-emerald-900/50 text-left transition flex flex-col gap-1">
            <span class="text-sm font-bold text-emerald-200">欧阳澈 (25岁)</span>
            <span class="text-xs text-stone-400">从八品 · 承务郎</span>
            <span class="text-[10px] text-emerald-300 mt-1">绿袍 · 短平角 · 无鱼袋 · 木笏</span>
          </button>
        </div>
      </div>

      <!-- 2. QQ 秀式自由换装实验室 (Paper Doll Dressing Room) -->
      <div class="bg-stone-950/70 rounded-xl border border-stone-800 p-4 shadow-sm flex flex-col gap-3">
        <div class="text-xs font-semibold text-amber-500 uppercase tracking-wider flex items-center justify-between">
          <span>2. 布娃娃插槽换装实验室 (Slot Decoupled Lab)</span>
          <span class="text-[10px] text-emerald-400">100% 骨骼物理贴合 · 绝无断头</span>
        </div>

        <!-- 素体底模 (Base Doll) -->
        <div>
          <label class="text-xs text-stone-400 block mb-1">人形素体 (Base Doll - 贴身白中单/顶束发髻)</label>
          <div class="grid grid-cols-3 gap-2">
            <button onclick="setSlot('doll', 'doll_young')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 hover:border-amber-500" data-slot="doll" data-val="doll_young">青年及第进士</button>
            <button onclick="setSlot('doll', 'doll_middle')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 hover:border-amber-500" data-slot="doll" data-val="doll_middle">中年知州帅臣</button>
            <button onclick="setSlot('doll', 'doll_elder')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 hover:border-amber-500" data-slot="doll" data-val="doll_elder">老年中枢宰辅</button>
          </div>
        </div>

        <!-- 官制大袍 (Robe) -->
        <div>
          <label class="text-xs text-stone-400 block mb-1">大袖圆领襕袍 (Robe - 开领对齐 y=360)</label>
          <div class="grid grid-cols-3 gap-2">
            <button onclick="setSlot('robe', 'robe_zi')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 hover:border-purple-500 text-purple-300" data-slot="robe" data-val="robe_zi">深绛紫袍 (一至三品)</button>
            <button onclick="setSlot('robe', 'robe_fei')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 hover:border-red-500 text-red-300" data-slot="robe" data-val="robe_fei">朱红绛袍 (四至五品)</button>
            <button onclick="setSlot('robe', 'robe_lv')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 hover:border-emerald-500 text-emerald-300" data-slot="robe" data-val="robe_lv">碧绿素袍 (六至七品)</button>
          </div>
        </div>

        <!-- 漆纱幞头 (Headwear) -->
        <div>
          <label class="text-xs text-stone-400 block mb-1">漆纱幞头 (Headwear - 基底扣齐 y=230)</label>
          <div class="grid grid-cols-2 gap-2">
            <button onclick="setSlot('futou', 'futou_long')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 hover:border-amber-500" data-slot="futou" data-val="futou_long">长直铁线两尺半展角</button>
            <button onclick="setSlot('futou', 'futou_short')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 hover:border-amber-500" data-slot="futou" data-val="futou_short">一尺半短窄平角</button>
          </div>
        </div>

        <!-- 随身佩鱼与手持 (Pouch & Held) -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-xs text-stone-400 block mb-1">随身鱼袋 (Pouch - 腰右 490,710)</label>
            <div class="flex flex-col gap-1.5">
              <button onclick="setSlot('pouch', 'pouch_gold')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 text-amber-300 text-left" data-slot="pouch" data-val="pouch_gold">纯金錾花金鱼袋</button>
              <button onclick="setSlot('pouch', 'pouch_silver')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 text-stone-300 text-left" data-slot="pouch" data-val="pouch_silver">白银锁扣银鱼袋</button>
              <button onclick="setSlot('pouch', 'none')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 text-stone-500 text-left" data-slot="pouch" data-val="none">不佩鱼 (无鱼袋)</button>
            </div>
          </div>
          <div>
            <label class="text-xs text-stone-400 block mb-1">胸前持物 (Held - 居中 405,520)</label>
            <div class="flex flex-col gap-1.5">
              <button onclick="setSlot('held', 'hu_ivory')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 text-stone-200 text-left" data-slot="held" data-val="hu_ivory">交趾光润象牙朝笏</button>
              <button onclick="setSlot('held', 'hu_wood')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 text-amber-600 text-left" data-slot="held" data-val="hu_wood">质朴端整槐木朝笏</button>
              <button onclick="setSlot('held', 'none')" class="btn-slot p-1.5 rounded text-xs border border-stone-700 bg-stone-900 text-stone-500 text-left" data-slot="held" data-val="none">空手端拱 (无手持)</button>
            </div>
          </div>
        </div>

      </div>

      <!-- 3. Shinsekai 召对语义与情绪联动模拟 -->
      <div class="bg-stone-950/70 rounded-xl border border-stone-800 p-4 shadow-sm">
        <div class="text-xs font-semibold text-amber-500 uppercase tracking-wider mb-2 flex items-center justify-between">
          <span>3. Shinsekai 召对语义联动模拟器</span>
          <span class="text-[10px] text-stone-400">AI 语义情感驱动状态机</span>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <button onclick="setEmotion('respectful', '恭谨肃立', '陛下睿断，臣等奉诏。')" class="p-2 rounded bg-stone-900 border border-stone-700 hover:border-emerald-500 text-xs text-left">
            <span class="text-emerald-400 block font-bold">恭谨肃立</span>
            <span class="text-[10px] text-stone-400">持笏端肃 · 官仪深重</span>
          </button>
          <button onclick="setEmotion('resolute', '刚直骨鲠', '事关宗社安危，臣死不敢奉诏！')" class="p-2 rounded bg-stone-900 border border-stone-700 hover:border-amber-500 text-xs text-left">
            <span class="text-amber-400 block font-bold">刚直直谏</span>
            <span class="text-[10px] text-stone-400">目光如炬 · 昂首力争</span>
          </button>
          <button onclick="setEmotion('worried', '忧国蹙眉', '边事孔亟，国库空虚，恐难支应。')" class="p-2 rounded bg-stone-900 border border-stone-700 hover:border-blue-500 text-xs text-left">
            <span class="text-blue-400 block font-bold">忧心忡忡</span>
            <span class="text-[10px] text-stone-400">微锁双眉 · 沉思机变</span>
          </button>
          <button onclick="setEmotion('panic', '惶恐引咎', '臣罪当万死，乞骸骨归田里。')" class="p-2 rounded bg-stone-900 border border-stone-700 hover:border-red-500 text-xs text-left">
            <span class="text-red-400 block font-bold">惶恐请罪</span>
            <span class="text-[10px] text-stone-400">双袖交抱 · 躬身敛首</span>
          </button>
          <button onclick="setEmotion('gratified', '欣慰受赏', '荷蒙圣恩，臣敢不夙夜忧勤！')" class="p-2 rounded bg-stone-900 border border-stone-700 hover:border-purple-500 text-xs text-left">
            <span class="text-purple-400 block font-bold">欣慰受命</span>
            <span class="text-[10px] text-stone-400">含笑从容 · 拜领恩旨</span>
          </button>
        </div>
        <div id="lbl_dialogue_quote" class="mt-3 p-2.5 rounded bg-stone-900/90 border border-amber-900/40 text-xs text-amber-200/90 italic">
          “陛下睿断，臣等奉诏。”
        </div>
      </div>

    </section>

  </main>

  <script>
    // 注入全部 16 种工笔透明图层 base64
    const ASSETS = {assets_json};

    // 当前换装插槽状态
    const state = {{
      doll: 'doll_elder',
      robe: 'robe_zi',
      futou: 'futou_long',
      pouch: 'pouch_gold',
      held: 'hu_ivory',
      motion: true
    }};

    // 预设名臣档案
    const PRESETS = {{
      cai_jing: {{
        title: '从一品 尚书左仆射兼门下侍郎',
        name: '蔡京',
        costume_tag: '深绛紫袍 · 金鱼袋',
        doll: 'doll_elder',
        robe: 'robe_zi',
        futou: 'futou_long',
        pouch: 'pouch_gold',
        held: 'hu_ivory'
      }},
      zhong_shizhong: {{
        title: '正四品 经略安抚使',
        name: '种师中',
        costume_tag: '朱红绛袍 · 银鱼袋',
        doll: 'doll_middle',
        robe: 'robe_fei',
        futou: 'futou_long',
        pouch: 'pouch_silver',
        held: 'hu_wood'
      }},
      new_scholar_ouyang: {{
        title: '从八品 承务郎',
        name: '欧阳澈',
        costume_tag: '碧绿素袍 · 短平角',
        doll: 'doll_young',
        robe: 'robe_lv',
        futou: 'futou_short',
        pouch: 'none',
        held: 'hu_wood'
      }}
    }};

    function updateView() {{
      // 更新图层 src
      document.getElementById('layer_bg').src = ASSETS.silk_bg;
      document.getElementById('layer_doll').src = ASSETS[state.doll] || '';
      document.getElementById('layer_robe').src = ASSETS[state.robe] || '';
      
      const pouchSrc = state.pouch !== 'none' ? ASSETS[state.pouch] : '';
      const pouchEl = document.getElementById('layer_pouch');
      pouchEl.src = pouchSrc;
      pouchEl.style.display = pouchSrc ? 'block' : 'none';

      const heldSrc = state.held !== 'none' ? ASSETS[state.held] : '';
      const heldEl = document.getElementById('layer_held');
      heldEl.src = heldSrc;
      heldEl.style.display = heldSrc ? 'block' : 'none';

      document.getElementById('layer_futou').src = ASSETS[state.futou] || '';

      // 高亮选中的按钮
      document.querySelectorAll('.btn-slot').forEach(btn => {{
        const slot = btn.getAttribute('data-slot');
        const val = btn.getAttribute('data-val');
        if (state[slot] === val) {{
          btn.classList.add('ring-2', 'ring-amber-500', 'bg-stone-800');
        }} else {{
          btn.classList.remove('ring-2', 'ring-amber-500', 'bg-stone-800');
        }}
      }});
    }}

    function setSlot(slot, val) {{
      state[slot] = val;
      updateView();
    }}

    function applyPreset(presetKey) {{
      const p = PRESETS[presetKey];
      if (!p) return;
      document.getElementById('lbl_minister_title').textContent = p.title;
      document.getElementById('lbl_minister_name').firstElementChild.textContent = p.name;
      document.getElementById('lbl_costume_tag').textContent = p.costume_tag;

      state.doll = p.doll;
      state.robe = p.robe;
      state.futou = p.futou;
      state.pouch = p.pouch;
      state.held = p.held;
      updateView();
    }}

    function setEmotion(code, label, quote) {{
      const badge = document.getElementById('lbl_emotion_badge');
      badge.textContent = `${{label}} (${{code}})`;
      document.getElementById('lbl_dialogue_quote').textContent = `“${{quote}}”`;

      // 情绪联动动效微调
      const dollEl = document.getElementById('layer_doll');
      const robeEl = document.getElementById('layer_robe');
      if (code === 'panic') {{
        dollEl.style.transform = 'translateY(12px) scale(0.98)';
        robeEl.style.transform = 'translateY(12px) scale(0.98)';
      }} else if (code === 'resolute') {{
        dollEl.style.transform = 'translateY(-6px) scale(1.01)';
        robeEl.style.transform = 'translateY(-6px) scale(1.01)';
      }} else {{
        dollEl.style.transform = '';
        robeEl.style.transform = '';
      }}
    }}

    document.getElementById('btn_toggle_motion').addEventListener('click', function() {{
      state.motion = !state.motion;
      const anims = document.querySelectorAll('.anim-breathe, .anim-futou');
      anims.forEach(el => {{
        el.style.animationPlayState = state.motion ? 'running' : 'paused';
      }});
      this.textContent = state.motion ? '暂停动效' : '恢复动效';
    }});

    // 初始化加载
    window.addEventListener('DOMContentLoaded', () => {{
      applyPreset('cai_jing');
    }});
  </script>
</body>
</html>
"""

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"展示台 HTML 构建成功: {OUT_HTML} (文件大小: {os.path.getsize(OUT_HTML)} 字节)")


if __name__ == "__main__":
    build_html()
