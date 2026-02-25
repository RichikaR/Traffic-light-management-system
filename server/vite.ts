import { type Express } from "express";
import { createServer as createViteServer, createLogger } from "vite";
import react from "@vitejs/plugin-react";
import { type Server } from "http";
import fs from "fs";
import path from "path";
import { nanoid } from "nanoid";

const viteLogger = createLogger();

export async function setupVite(server: Server, app: Express) {
  const serverOptions = {
    middlewareMode: true,
    hmr: { server, path: "/vite-hmr" },
    allowedHosts: true as const,
  };

  const projectRoot = path.resolve(import.meta.dirname, "..");
  const clientRoot = path.join(projectRoot, "client");

  const vite = await createViteServer({
    root: clientRoot,
    configFile: false,
    appType: "custom",
    server: serverOptions,

    plugins: [
      react({
        jsxRuntime: "automatic",
      }),
    ],

    resolve: {
      alias: {
        "@": path.join(clientRoot, "src"),
        "@shared": path.join(projectRoot, "shared"),
      },
    },

    customLogger: {
      ...viteLogger,
      error: (msg, options) => {
        viteLogger.error(msg, options);
        process.exit(1);
      },
    },
  });

  app.use(vite.middlewares);

  app.use("*", async (req, res, next) => {
    try {
      const url = req.originalUrl;
      const templatePath = path.join(clientRoot, "index.html");
      let template = await fs.promises.readFile(templatePath, "utf-8");

      template = template.replace(
        `src="/src/main.tsx"`,
        `src="/src/main.tsx?v=${nanoid()}"`
      );

      const html = await vite.transformIndexHtml(url, template);
      res.status(200).set({ "Content-Type": "text/html" }).end(html);
    } catch (e) {
      vite.ssrFixStacktrace(e as Error);
      next(e);
    }
  });
}

