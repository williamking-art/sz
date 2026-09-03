/* -*- coding: utf-8 -*-
 * 宋祚 · MapLibre Web 舆图应用逻辑
 *
 * 数据源（同目录，经本地 HTTP 服务提供，禁 file:// 直开）：
 *   circuits.geojson  18 路  Polygon  {name,type,seat,member_count,game_unit}
 *   regimes.geojson   14 政权 + 分路 Polygon  {name,display_name,active,always_show,
 *                     label_at,note,owner} / 分路 {kind:"sub",parent,owner,seat,seat_at,label_at}
 *   cities.geojson    116 治所 Point   {name,level,circuit,is_seat,game_unit}
 *   view.json         fitBounds 四至
 *
 * 桥接协议（与 ui/map_web.py 对应）：
 *   JS→Python  window.pywebview.api.map_ready/feature_click/map_event(payload)
 *              浏览器降级：POST /bridge {method,payload}
 *   Python→JS  window.SongZuoMap.applyState(state)
 *              浏览器降级：轮询 GET /state?since=seq
 */
(function () {
  "use strict";

  // ---------------- 主题（与 ui/theme.py 一致） ----------------
  var C = {
    paper: "#f1e5c8",        // 地图底（比 HUD 宣纸略深，衬托图层）
    ink: "#2b1d12",
    inkLight: "#5a4a3a",
    red: "#8a2b22",
    gold: "#caa24a",
    goldDark: "#8f6e28",
    // 路（宋行政区划）三型底色
    cJijing: "#efd9a8",      // 京畿
    cFuli: "#f3e7c6",        // 腹里
    cYanbian: "#eddfba",     // 沿边
    cRegime: "#d8cbaa",      // 境外政权
    cRegimeOff: "#e3dbc8",   // 未兴（金开局 inactive）
    cLineRegime: "#6b5b45",
    cCitySeat: "#8a2b22",
    cCityTown: "#4a3a28",
    // 底图（真实地理）：海面 / 陆地晕染 / 河湖
    sea: "#b0bfb6",
    landGold: "#e3c27f",
    river: "#4f7f8e"
  };

  // 标签显隐档位（zoom 阈值）
  var TIER = { regime: 0, sub: 3.2, jingfu: 3.0, seat: 3.4, circuit: 4.0, town: 4.6 };

  var S = {
    map: null,
    data: { circuits: null, regimes: null, cities: null,
            land: null, rivers: null, lakes: null, borders: null },
    view: null,
    labels: [],            // {el, tier, visible} visible=数据侧可见（如未兴政权）
    customMarkers: [],
    pulseMarker: null,
    selected: null,        // {kind, name, source, id}
    hover: {},             // layerId -> feature id
    activeExtra: [],       // applyState 强制显示的政权（如 金）
    hiddenRegimes: [],     // applyState 强制隐藏的政权（如 辽收缩）
    seq: 0,
    bridgeMode: "boot",
    ready: false
  };

  // ---------------- 工具 ----------------
  function $(id) { return document.getElementById(id); }

  function showError(title, detail) {
    var veil = $("veil");
    veil.classList.add("err");
    veil.classList.remove("hide");
    $("errbox").innerHTML = "<b>" + title + "</b><br>" + detail +
      '<br><span class="retry" onclick="location.reload()">重试</span>';
  }

  function bboxOfRing(ring) {
    var x0 = 180, y0 = 90, x1 = -180, y1 = -90;
    for (var i = 0; i < ring.length; i++) {
      var p = ring[i];
      if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
      if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
    }
    return [x0, y0, x1, y1];
  }

  // 取要素外环 bbox 中心（数据均为凸近似的简化多边形，bbox 中心即视觉中心）
  function centerOf(feature) {
    var g = feature.geometry;
    var rings = [];
    if (g.type === "Polygon") rings = [g.coordinates[0]];
    else if (g.type === "MultiPolygon") {
      g.coordinates.forEach(function (poly) { rings.push(poly[0]); });
    } else if (g.type === "Point") return g.coordinates.slice();
    var best = null, bestArea = -1;
    rings.forEach(function (r) {
      var b = bboxOfRing(r);
      var a = (b[2] - b[0]) * (b[3] - b[1]);
      if (a > bestArea) { bestArea = a; best = b; }
    });
    return best ? [(best[0] + best[2]) / 2, (best[1] + best[3]) / 2] : [0, 0];
  }

  function bboxOfFeature(feature) {
    var g = feature.geometry, b = null;
    if (g.type === "Point") return [g.coordinates[0] - .4, g.coordinates[1] - .4,
                                    g.coordinates[0] + .4, g.coordinates[1] + .4];
    var rings = g.type === "Polygon" ? [g.coordinates[0]] :
      g.coordinates.map(function (p) { return p[0]; });
    rings.forEach(function (r) {
      var rb = bboxOfRing(r);
      b = b ? [Math.min(b[0], rb[0]), Math.min(b[1], rb[1]),
               Math.max(b[2], rb[2]), Math.max(b[3], rb[3])] : rb;
    });
    return b;
  }

  // ---------------- 桥接客户端 ----------------
  var Bridge = {
    call: function (method, payload) {
      payload = payload || {};
      if (window.pywebview && window.pywebview.api &&
          typeof window.pywebview.api[method] === "function") {
        S.bridgeMode = "pywebview";
        try {
          var r = window.pywebview.api[method](payload);
          if (r && typeof r.catch === "function") {
            r.catch(function (e) { console.warn("[bridge]", method, e); });
          }
        } catch (e) { console.warn("[bridge]", method, e); }
        return;
      }
      // 浏览器降级：HTTP 桥
      fetch("/bridge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ method: method, payload: payload })
      }).catch(function (e) { console.warn("[bridge-http]", method, e); });
    },
    // 等待 pywebview 注入；超时则进入浏览器轮询模式
    detect: function () {
      function ok() {
        return !!(window.pywebview && window.pywebview.api &&
                  typeof window.pywebview.api.map_ready === "function");
      }
      return new Promise(function (resolve) {
        if (ok()) { S.bridgeMode = "pywebview"; return resolve(); }
        window.addEventListener("pywebviewready", function () {
          if (ok()) { S.bridgeMode = "pywebview"; resolve(); }
        });
        var tries = 0;
        var t = setInterval(function () {
          tries += 1;
          if (ok()) { clearInterval(t); S.bridgeMode = "pywebview"; resolve(); }
          else if (tries >= 14) { clearInterval(t); S.bridgeMode = "http"; resolve(); }
        }, 100);
      });
    },
    // 浏览器模式：轮询 Python 下发的状态
    poll: function () {
      if (S.bridgeMode !== "http" || !S.ready) return;
      fetch("/state?since=" + S.seq)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.seq > S.seq) { S.seq = d.seq; SongZuoMap.applyState(d.state || {}); }
        })
        .catch(function () {})
        .then(function () { setTimeout(Bridge.poll, 900); });
    }
  };

  // ---------------- 样式与图层 ----------------
  function regimeFilter() {
    // 显示：active=true 或被 applyState 强制显示；且不在强制隐藏名单
    var show = ["any", ["get", "active"]];
    if (S.activeExtra.length) {
      show.push(["in", ["get", "name"], ["literal", S.activeExtra]]);
    }
    var f = ["all", show];
    if (S.hiddenRegimes.length) {
      f.push(["!", ["in", ["get", "name"], ["literal", S.hiddenRegimes]]]);
    }
    return f;
  }

  function subFilter() {
    // 分路（kind="sub"）显隐：母政权可见则显示；母被隐藏（如辽收缩）时，
    // 已易主宋或其他仍显示政权的分路仍显示（地随主走，不随旧母消失）
    var f = ["all", ["==", ["get", "kind"], "sub"]];
    var keep = ["any",
      ["!", ["in", ["get", "parent"], ["literal", S.hiddenRegimes]]],
      ["==", ["get", "owner"], "宋"]];
    if (S.activeExtra.length) {
      keep.push(["in", ["get", "owner"], ["literal", S.activeExtra]]);
    }
    f.push(keep);
    return f;
  }

  // 政权渲染色（单一推导点）：按 active 推导；引入 per-owner 色板时只改本函数。
  function regimeColorOf(props) {
    return props && props.active ? C.cRegime : C.cRegimeOff;
  }

  // 分路填充色表达式：按分路自身 owner 取色（宋地用腹里色，境外按其归属
  // 政权推导）；["match", owner, 宋, 色, 政权1, 色1, ..., fallback]
  function subColorExpr() {
    var stops = [];
    var seen = { "宋": true };
    S.data.regimes.features.forEach(function (f) {
      var p = f.properties;
      if (!p || p.kind === "sub" || seen[p.name]) return;
      seen[p.name] = true;
      stops.push(p.name, regimeColorOf(p));
    });
    return ["match", ["get", "owner"]].concat(
      ["宋", C.cFuli], stops, [C.cRegime]);
  }

  // 分路 owner 或政权 active 变化后重算分路取色（不重建图层，仅刷 paint）
  function refreshSubColors() {
    if (!S.map || !S.map.getLayer("sub-fill")) return;
    S.map.setPaintProperty("sub-fill", "fill-color", subColorExpr());
  }

  function buildStyle() {
    return {
      version: 8,
      // 离线：不用 symbol 文本层，故不设 glyphs（设 undefined 会过不了样式校验，
      // 导致 load 永不触发、页面永远停在"绘制中"）
      sources: {
        regimes: { type: "geojson", data: S.data.regimes },
        circuits: { type: "geojson", data: S.data.circuits },
        cities: { type: "geojson", data: S.data.cities },
        land: { type: "geojson", data: S.data.land },
        rivers: { type: "geojson", data: S.data.rivers },
        lakes: { type: "geojson", data: S.data.lakes },
        borders: { type: "geojson", data: S.data.borders },
        hill: {
          type: "raster",
          tiles: ["./tiles/hill/{z}/{x}/{y}.png"],
          tileSize: 256,
          minzoom: 4,
          maxzoom: 8
        }
      },
      layers: [
        // ---- 底图（真实地理）：海面 → 陆地 → 地形晕渲 → 河湖 ----
        { id: "bg", type: "background", paint: { "background-color": C.sea } },
        {
          id: "land-fill", type: "fill", source: "land",
          paint: {
            "fill-color": C.landGold,
            "fill-opacity": 0.9,
            "fill-outline-color": "transparent"
          }
        },
        {
          id: "hill", type: "raster", source: "hill",
          paint: { "raster-opacity": 0.42 }
        },
        {
          id: "river-line", type: "line", source: "rivers",
          paint: {
            "line-color": C.river,
            "line-width": ["interpolate", ["linear"],
              ["coalesce", ["get", "scalerank"], 9],
              3, 1.6, 6, 1.0, 9, 0.6, 12, 0.35],
            "line-opacity": 0.8
          }
        },
        {
          id: "lake-fill", type: "fill", source: "lakes",
          paint: {
            "fill-color": C.river,
            "fill-opacity": 0.65,
            "fill-outline-color": "transparent"
          }
        },
        // ---- 境外政权（L0 舆图底） ----
        {
          id: "regime-fill", type: "fill", source: "regimes",
          filter: regimeFilter(),
          paint: {
            "fill-color": ["case", ["get", "active"], C.cRegime, C.cRegimeOff],
            "fill-opacity": ["case",
              ["boolean", ["feature-state", "selected"], false], 0.62,
              ["boolean", ["feature-state", "hover"], false], 0.52, 0.34]
          }
        },
        {
          id: "regime-line", type: "line", source: "regimes",
          filter: regimeFilter(),
          paint: {
            "line-color": ["case",
              ["boolean", ["feature-state", "selected"], false], C.red, C.cLineRegime],
            "line-width": ["case",
              ["boolean", ["feature-state", "selected"], false], 2.0, 1.1],
            "line-dasharray": [4, 3],
            "line-opacity": 0.75
          }
        },
        // ---- 政权内部分路（叠于政权填充之上、宋诸路之下；虚线示内部界） ----
        {
          id: "sub-fill", type: "fill", source: "regimes",
          filter: subFilter(),
          paint: {
            "fill-color": subColorExpr(),   // 按分路自身 owner 取色
            "fill-opacity": ["case",
              ["boolean", ["feature-state", "selected"], false], 0.5,
              ["boolean", ["feature-state", "hover"], false], 0.42, 0.22]
          }
        },
        {
          id: "sub-line", type: "line", source: "regimes",
          filter: subFilter(),
          paint: {
            "line-color": C.cLineRegime,
            "line-width": ["case",
              ["boolean", ["feature-state", "selected"], false], 1.6, 0.9],
            "line-dasharray": [2, 2],       // 内部界用细虚线，区别于政权外缘
            "line-opacity": 0.6
          }
        },
        // ---- 宋诸路 ----
        {
          id: "circuit-fill", type: "fill", source: "circuits",
          paint: {
            "fill-color": ["match", ["get", "type"], "京畿", C.cJijing,
                           "沿边", C.cYanbian, C.cFuli],
            "fill-opacity": ["case",
              ["boolean", ["feature-state", "selected"], false], 0.92,
              ["boolean", ["feature-state", "hover"], false], 0.78, 0.55],
            "fill-outline-color": "transparent"
          }
        },
        {
          // 地级政区细界（路内分界，弱化）
          id: "circuit-line", type: "line", source: "circuits",
          paint: {
            "line-color": "#8a7a5c",
            "line-width": 0.45,
            "line-opacity": 0.55
          }
        },
        {
          // 路级粗界（真政区并集外缘）
          id: "circuit-border-line", type: "line", source: "borders",
          paint: {
            "line-color": ["case",
              ["boolean", ["feature-state", "selected"], false], C.red, "#6b5b45"],
            "line-width": ["case",
              ["boolean", ["feature-state", "selected"], false], 2.2,
              ["==", ["get", "type"], "京畿"], 1.8, 1.1],
            "line-opacity": ["case",
              ["boolean", ["feature-state", "selected"], false], 0.95, 0.75]
          }
        },
        // ---- 治所点 ----
        {
          id: "city-circle", type: "circle", source: "cities",
          paint: {
            "circle-radius": ["case",
              ["boolean", ["feature-state", "selected"], false], 8.0,
              ["boolean", ["feature-state", "hover"], false], 7.0,
              ["match", ["get", "level"], "京府", 6.2, "府", 5.2, "军", 4.2, 4.6]],
            "circle-color": ["case", ["get", "is_seat"], C.cCitySeat, C.cCityTown],
            "circle-stroke-color": ["case", ["get", "is_seat"], C.gold, C.paper],
            "circle-stroke-width": ["case", ["get", "is_seat"], 1.6, 1.0],
            "circle-opacity": ["case", ["get", "is_seat"], 1.0, 0.85]
          }
        }
      ]
    };
  }

  // ---------------- 标签 Marker（HTML，无 glyphs） ----------------
  function addLabel(lngLat, text, cls, tier, visible, onClick, meta) {
    var el = document.createElement("div");
    el.className = "lbl " + cls;
    el.textContent = text;
    if (onClick) el.addEventListener("click", function (e) {
      e.stopPropagation(); onClick();
    });
    var mk = new maplibregl.Marker({ element: el, anchor: "center" })
      .setLngLat(lngLat).addTo(S.map);
    var rec = { el: el, tier: tier, visible: visible !== false,
                kind: meta && meta.kind, name: meta && meta.name,
                parent: meta && meta.parent, owner: meta && meta.owner };
    S.labels.push(rec);
    return mk;
  }

  function buildLabels() {
    // 政权标签：用 label_at 权威点位
    S.data.regimes.features.forEach(function (f) {
      var p = f.properties;
      if (p.kind === "sub") return;   // 分路标签在政权标签之后统一建
      var at = p.label_at || centerOf(f);
      var on = !!p.active;
      addLabel(at, p.display_name || p.name, "lbl-regime" + (on ? "" : " off"),
        TIER.regime, on, function () { selectFeature("regime", p.name); },
        { kind: "regime", name: p.name });
    });
    // 分路标签：label_at 权威点位；小一号（内联缩字号，CSS 不动）
    S.data.regimes.features.forEach(function (f) {
      var p = f.properties;
      if (p.kind !== "sub") return;
      var at = p.label_at || centerOf(f);
      var mk = addLabel(at, p.name, "lbl-circuit", TIER.sub, true,
        function () { selectFeature("sub", p.name); },
        { kind: "sub", name: p.name, parent: p.parent, owner: p.owner });
      var el = mk.getElement();
      el.style.fontSize = "10.5px";
      el.style.letterSpacing = "1.5px";
      el.style.color = "#6b5b45";
    });
    // 路标签：实界并集 representative point
    S.data.borders.features.forEach(function (f) {
      var p = f.properties;
      addLabel(p.label_at, p.name, "lbl-circuit", TIER.circuit, true,
        function () { selectFeature("circuit", p.name); });
    });
    // 治所标签
    S.data.cities.features.forEach(function (f) {
      var p = f.properties;
      var seat = !!p.is_seat;
      var cls = "lbl-city" + (seat ? " seat" : "") + (p.level === "京府" ? " jingfu" : "");
      var tier = p.level === "京府" ? TIER.jingfu : (seat ? TIER.seat : TIER.town);
      addLabel(f.geometry.coordinates, p.name, cls, tier, true,
        function () { selectFeature("city", p.name); });
    });
    refreshLabels();
  }

  function refreshLabels() {
    if (!S.map) return;
    var z = S.map.getZoom();
    S.labels.forEach(function (l) {
      var show = l.visible && z >= l.tier;
      l.el.classList.toggle("lbl-hidden", !show);
    });
  }

  // 政权 active 状态变化后，同步标签可见性（含分路标签随母政权）
  function refreshRegimeLabels() {
    var extra = {};
    S.activeExtra.forEach(function (n) { extra[n] = true; });
    var hidden = {};
    S.hiddenRegimes.forEach(function (n) { hidden[n] = true; });
    var regimeOn = {};
    S.data.regimes.features.forEach(function (f) {
      var p = f.properties;
      if (p.kind === "sub") return;
      regimeOn[p.name] = (!!p.active || !!extra[p.name]) && !hidden[p.name];
    });
    S.labels.forEach(function (lab) {
      var on;
      if (lab.kind === "regime") on = regimeOn[lab.name];
      else if (lab.kind === "sub") {
        // 分路标签随其归属：母可见，或已易主宋/仍显示政权
        on = regimeOn[lab.parent] || lab.owner === "宋" || !!regimeOn[lab.owner];
      }
      else return;
      lab.visible = on;
      lab.el.classList.toggle("off", !on);
    });
    refreshLabels();
  }

  // ---------------- 选中 / 悬停 ----------------
  function clearSelected() {
    if (S.selected) {
      var ids = S.selected.ids ||
        (S.selected.id != null ? [S.selected.id] : []);
      ids.forEach(function (id) {
        S.map.setFeatureState(
          { source: S.selected.source, id: id }, { selected: false });
      });
    }
    S.selected = null;
    if (S.pulseMarker) { S.pulseMarker.remove(); S.pulseMarker = null; }
    $("card").classList.remove("show");
  }

  function findFeature(kind, name) {
    var key = { city: "cities", circuit: "circuits", regime: "regimes",
                sub: "regimes" }[kind];
    if (!key || !S.data[key]) return null;
    var arr = S.data[key].features;
    for (var i = 0; i < arr.length; i++) {
      var p = arr[i].properties;
      if (p.kind === "sub" !== (kind === "sub")) continue; // 同名互斥：分路/母分查
      if (p.name === name || (kind === "regime" && p.display_name === name)) {
        return { feature: arr[i], id: arr[i].id, source: key };
      }
    }
    return null;
  }

  // 母政权 feature 查找（分路信息卡/取色用）
  function parentFeatureOf(parent) {
    var arr = S.data.regimes.features;
    for (var i = 0; i < arr.length; i++) {
      var p = arr[i].properties;
      if (p.kind !== "sub" && p.name === parent) return arr[i];
    }
    return null;
  }

  function showCard(kind, p) {
    var kindText = { city: "城池", circuit: "诸路", regime: "政权",
                     sub: "分路" }[kind] || "";
    $("card-kind").textContent = kindText;
    $("card-title").textContent =
      (kind === "regime" ? (p.display_name || p.name) : p.name) || "";
    var rows = [];
    function kv(k, v) {
      if (v === undefined || v === null || v === "") return;
      rows.push('<div class="kv"><span class="k">' + k + '</span><span class="v">' + v + "</span></div>");
    }
    if (kind === "city") {
      kv("等级", p.level);
      kv("所属路", p.circuit);
      kv("职任", p.is_seat ? "路治所" : "属城");
      kv("辖属", p.game_unit);
    } else if (kind === "circuit") {
      kv("类型", p.type);
      kv("治所", p.seat);
      kv("属城", p.member_count);
      kv("辖属", p.game_unit);
    } else if (kind === "sub") {
      var pf = parentFeatureOf(p.parent);
      kv("所属政权", pf ? (pf.properties.display_name || pf.properties.name) : p.parent);
      kv("治所", p.seat);
      kv("归属", p.owner || p.parent);  // 分路自持 owner，可与母政权不同
    } else {
      kv("状态", p.active ? "在位" : "未兴");
      kv("主号", p.owner);
    }
    var note = p.note ? '<div class="note">' + p.note + "</div>" : "";
    $("card-body").innerHTML = rows.join("") + note;
    $("card").classList.add("show");
  }

  function selectFeature(kind, name, opts) {
    opts = opts || {};
    var hit = findFeature(kind, name);
    if (!hit) return false;
    clearSelected();
    var f = hit.feature, p = f.properties;
    // 路 = 多政区合并体：整路高亮（同路全部政区一并置选中态）
    var ids = [];
    if (kind === "circuit") {
      S.data.circuits.features.forEach(function (ft) {
        if (ft.properties.name === name && ft.id != null) ids.push(ft.id);
      });
    } else if (hit.id != null) {
      ids = [hit.id];
    }
    S.selected = { kind: kind, name: name, source: hit.source, id: hit.id,
                   ids: ids };
    ids.forEach(function (id) {
      S.map.setFeatureState({ source: hit.source, id: id },
        { selected: true });
    });
    if (kind === "city") {
      var el = document.createElement("div");
      el.className = "pulse";
      S.pulseMarker = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat(f.geometry.coordinates).addTo(S.map);
    }
    showCard(kind, p);
    if (opts.fly) {
      var b = bboxOfFeature(f);
      if (kind === "circuit") {
        // 飞行视野取整路并集 bbox
        S.data.circuits.features.forEach(function (ft) {
          if (ft.properties.name !== name) return;
          var bb = bboxOfFeature(ft);
          if (bb[0] < b[0]) b[0] = bb[0];
          if (bb[1] < b[1]) b[1] = bb[1];
          if (bb[2] > b[2]) b[2] = bb[2];
          if (bb[3] > b[3]) b[3] = bb[3];
        });
      }
      S.map.fitBounds([[b[0], b[1]], [b[2], b[3]]],
        { padding: 90, maxZoom: 5.4, duration: 620 });
    }
    Bridge.call("feature_click", {
      kind: kind, name: name,
      props: { level: p.level, circuit: p.circuit, is_seat: p.is_seat,
               type: p.type, seat: p.seat, member_count: p.member_count,
               game_unit: p.game_unit, active: p.active, owner: p.owner,
               display_name: p.display_name, note: p.note,
               kind: p.kind, parent: p.parent },
      lnglat: kind === "city" ? f.geometry.coordinates : centerOf(f)
    });
    return true;
  }

  function setHover(layerId, feat) {
    var prev = S.hover[layerId];
    if (prev !== undefined && prev !== null &&
        !(feat && feat.id === prev)) {
      S.map.setFeatureState({ source: featSourceOf(layerId), id: prev },
        { hover: false });
    }
    S.hover[layerId] = feat ? feat.id : null;
    if (feat && feat.id != null) {
      S.map.setFeatureState({ source: featSourceOf(layerId), id: feat.id },
        { hover: true });
    }
  }

  function featSourceOf(layerId) {
    return layerId.indexOf("city") === 0 ? "cities"
      : layerId.indexOf("circuit") === 0 ? "circuits" : "regimes";
  }

  function bindInteractions() {
    var interactive = ["city-circle", "circuit-fill", "regime-fill", "sub-fill"];
    var map = S.map;
    map.on("mousemove", function (e) {
      var feats = map.queryRenderedFeatures(e.point,
        { layers: interactive });
      var byLayer = {};
      feats.forEach(function (f) { byLayer[f.layer.id] = f; });
      interactive.forEach(function (lid) { setHover(lid, byLayer[lid] || null); });
      map.getCanvas().style.cursor = feats.length ? "pointer" : "";
    });
    map.on("mouseout", function () {
      interactive.forEach(function (lid) { setHover(lid, null); });
    });
    map.on("click", function (e) {
      var feats = map.queryRenderedFeatures(e.point,
        { layers: interactive });
      if (!feats.length) {
        if (S.selected) {
          clearSelected();
          Bridge.call("map_event", { kind: "selection_cleared" });
        }
        return;
      }
      var f = feats[0];
      var lid = f.layer.id;
      var kind = lid === "sub-fill" ? "sub"
        : lid.indexOf("city") === 0 ? "city"
        : lid.indexOf("circuit") === 0 ? "circuit" : "regime";
      selectFeature(kind, f.properties.name);
    });
    map.on("zoomend", refreshLabels);
    map.on("moveend", refreshLabels);
  }

  // ---------------- Python → JS 状态应用 ----------------
  var SongZuoMap = {
    applyState: function (state) {
      if (!state || typeof state !== "object") return;
      try { applyStateInner(state); } catch (e) { console.warn("[applyState]", e); }
    },
    select: function (kind, name) { return selectFeature(kind, name, { fly: true }); },
    resetView: function () { fitInitial(); }
  };
  window.SongZuoMap = SongZuoMap;

  function applyStateInner(state) {
    if (state.hud) {
      var h = state.hud, parts = [];
      if (h.era) parts.push(h.era);
      if (h.year !== undefined && h.year !== null) {
        var y = h.year + " 年";
        if (h.month !== undefined && h.month !== null) y += " " + h.month + " 月";
        parts.push(y);
      }
      if (h.season) parts.push(h.season);
      $("hud-era").textContent = parts.join(" · ") || "—";
    }
    var needRegimeRefresh = false;
    if (Array.isArray(state.active_regimes)) {
      S.activeExtra = state.active_regimes;
      S.map.setFilter("regime-fill", regimeFilter());
      S.map.setFilter("regime-line", regimeFilter());
      S.map.setFilter("sub-fill", subFilter());
      S.map.setFilter("sub-line", subFilter());
      needRegimeRefresh = true;
    }
    if (Array.isArray(state.hidden_regimes)) {
      S.hiddenRegimes = state.hidden_regimes;
      S.map.setFilter("regime-fill", regimeFilter());
      S.map.setFilter("regime-line", regimeFilter());
      S.map.setFilter("sub-fill", subFilter());
      S.map.setFilter("sub-line", subFilter());
      needRegimeRefresh = true;
    }
    if (state.sub_owners && typeof state.sub_owners === "object") {
      // 分路易主（宋取燕云等）：改写 feature owner 后刷色/刷显隐
      var feats = S.data.regimes.features;
      Object.keys(state.sub_owners).forEach(function (n) {
        for (var i = 0; i < feats.length; i++) {
          var p = feats[i].properties;
          if (p && p.kind === "sub" && p.name === n) {
            p.owner = state.sub_owners[n]; break;
          }
        }
      });
      needRegimeRefresh = true;
    }
    if (state.regime_owners && typeof state.regime_owners === "object") {
      // 政权易主（金崛起代辽等）：改写主号展示
      var rfeats = S.data.regimes.features;
      Object.keys(state.regime_owners).forEach(function (n) {
        for (var i = 0; i < rfeats.length; i++) {
          var p = rfeats[i].properties;
          if (p && p.kind !== "sub" && p.name === n) {
            p.owner = state.regime_owners[n]; break;
          }
        }
      });
      needRegimeRefresh = true;
    }
    if (needRegimeRefresh) {
      refreshSubColors();      // 分路/政权 owner 或显隐变化 → 重算分路取色
      refreshRegimeLabels();
    }
    if (Array.isArray(state.markers)) applyMarkers(state.markers);
    if (state.focus) applyFocus(state.focus);
    if (state.select === null) clearSelected();
    else if (state.select && state.select.kind && state.select.name) {
      selectFeature(state.select.kind, state.select.name, { fly: true });
    }
  }

  function applyMarkers(markers) {
    S.customMarkers.forEach(function (m) { m.remove(); });
    S.customMarkers = [];
    (markers || []).forEach(function (m) {
      if (!m || !isFinite(m.lng) || !isFinite(m.lat)) return;
      var el = document.createElement("div");
      el.className = "seal-mk";
      el.innerHTML = '<div class="sq' + (m.kind === "warn" ? " warn" : "") +
        '"></div><div class="tx"></div>';
      el.querySelector(".tx").textContent = m.label || "";
      var mk = new maplibregl.Marker({ element: el, anchor: "bottom" })
        .setLngLat([m.lng, m.lat]).addTo(S.map);
      S.customMarkers.push(mk);
    });
  }

  function applyFocus(f) {
    if (Array.isArray(f.bounds) && f.bounds.length === 4) {
      S.map.fitBounds([[f.bounds[0], f.bounds[1]], f.bounds.slice(2)],
        { padding: f.padding || 70, maxZoom: f.maxZoom || 6.5, duration: 620 });
    } else if (isFinite(f.lng) && isFinite(f.lat)) {
      S.map.flyTo({ center: [f.lng, f.lat], zoom: f.zoom || 4.6, duration: 620 });
    }
  }

  function fitInitial() {
    var v = S.view || {};
    if (Array.isArray(v.bounds) && v.bounds.length === 4) {
      S.map.fitBounds([[v.bounds[0], v.bounds[1]], [v.bounds[2], v.bounds[3]]],
        { padding: 36, duration: 0 });
    } else {
      S.map.jumpTo({ center: v.center || [97.5, 22], zoom: v.zoom || 2.6 });
    }
  }

  // ---------------- 启动 ----------------
  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + " → HTTP " + r.status);
      return r.json();
    });
  }

  function boot() {
    if (typeof maplibregl === "undefined") {
      showError("地图库加载失败", "maplibre-gl.js 缺失或损坏，请检查 assets/map/web/ 资源完整性。");
      return;
    }
    Promise.all([
      fetchJson("./view.json"),
      fetchJson("./circuits.geojson"),
      fetchJson("./regimes.geojson"),
      fetchJson("./cities.geojson"),
      fetchJson("./land.geojson"),
      fetchJson("./rivers.geojson"),
      fetchJson("./lakes.geojson"),
      fetchJson("./circuit_borders.geojson")
    ]).then(function (rs) {
      S.view = rs[0];
      // 预分配稳定 feature id（顶层 id），供 feature-state / 选中态使用
      ["circuits", "regimes", "cities", "land", "rivers", "lakes", "borders"]
        .forEach(function (k, i) {
          S.data[k] = rs[i + 1];
          S.data[k].features.forEach(function (f, j) { f.id = j; });
        });
      S.map = new maplibregl.Map({
        container: "map",
        style: buildStyle(),
        center: [97.5, 22],
        zoom: 2.6,
        minZoom: 2.2,
        maxZoom: 8,
        attributionControl: false,
        doubleClickZoom: true
      });
      S.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      S.map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: "metric" }), "bottom-right");
      S.map.on("load", onMapLoad);
      S.map.on("error", function (e) {
        console.warn("[maplibre]", e && e.error);
        // 初始化期错误（如样式校验失败会阻断 load）直接上错误幕，不让用户干等
        if (!S.ready) {
          showError("舆图初始化失败",
            String((e && e.error && e.error.message) || (e && e.error) || e));
        }
      });
    }).catch(function (e) {
      showError("舆图数据加载失败", String(e && e.message || e) +
        "<br>请确认经由宋祚程序（本地服务）打开，而非直接双击本文件。");
    });
  }

  function onMapLoad() {
    fitInitial();
    buildLabels();
    bindInteractions();
    // UI 事件
    $("btn-reset").addEventListener("click", fitInitial);
    $("card-x").addEventListener("click", function () {
      clearSelected();
      Bridge.call("map_event", { kind: "selection_cleared" });
    });
    $("legend-head").addEventListener("click", function () {
      $("legend").classList.toggle("closed");
    });
    // 就绪上报
    S.ready = true;
    Bridge.detect().then(function () {
      Bridge.call("map_ready", {
        cities: S.data.cities.features.length,
        circuits: S.data.borders.features.length,
        regimes: S.data.regimes.features.length,
        subs: S.data.regimes.features.filter(function (f) {
          return f.properties.kind === "sub";
        }).length,
        mode: S.bridgeMode
      });
      Bridge.poll();
    });
    var veil = $("veil");
    veil.classList.add("hide");
    setTimeout(function () { veil.style.display = "none"; }, 600);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
