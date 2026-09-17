/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/renderer/index.html", "./src/renderer/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f6ecd6",
        "paper-dark": "#efe2c4",
        ink: "#1c120c",
        "ink-light": "#423224",
        red: "#8a2b22",
        "red-dark": "#7a1f1f",
        gold: "#caa24a",
        "gold-light": "#e8d49c",
        "gold-dark": "#8f6e28",
        card: "#fffaf0",
        dim: "#75552b",
        border: "#d8c08a"
      },
      fontFamily: {
        kai: [
          '"Source Han Serif SC"',
          '"Noto Serif SC"',
          '"Songti SC"',
          '"SimSun"',
          '"STSong"',
          '"KaiTi"',
          '"STKaiti"',
          '"楷体"',
          "serif"
        ],
        sans: [
          '"Microsoft YaHei"',
          '"微软雅黑"',
          '"PingFang SC"',
          "sans-serif"
        ]
      },
      boxShadow: {
        paper: "0 2px 10px rgba(43,29,18,.22), inset 0 0 0 1px rgba(232,212,156,.6)",
        card: "0 4px 16px rgba(43,29,18,.3), inset 0 0 0 1px rgba(232,212,156,.5)"
      },
      keyframes: {
        "card-in": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "none" }
        },
        pulse: {
          "0%": { transform: "scale(.55)", opacity: ".9" },
          "70%": { transform: "scale(1.15)", opacity: "0" },
          "100%": { opacity: "0" }
        },
        breathe: {
          "0%,100%": { boxShadow: "0 0 0 0 rgba(138,43,34,.45)" },
          "50%": { boxShadow: "0 0 0 8px rgba(138,43,34,0)" }
        }
      },
      animation: {
        "card-in": "card-in .22s ease-out",
        pulse: "pulse 1.6s ease-out infinite",
        breathe: "breathe 2.2s ease-in-out infinite"
      }
    }
  },
  plugins: [require("tailwindcss-animate")]
};