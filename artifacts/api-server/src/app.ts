import express, { type Express } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import router from "./routes";
import { logger } from "./lib/logger";
import { KILL_SERVER_PORT } from "./lib/trader";

const app: Express = express();

app.use(
  pinoHttp({
    logger,
    serializers: {
      req(req) {
        return {
          id: req.id,
          method: req.method,
          url: req.url?.split("?")[0],
        };
      },
      res(res) {
        return {
          statusCode: res.statusCode,
        };
      },
    },
  }),
);
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use("/api", router);

// Kill-switch control panel — proxied to the Python trading loop's
// control server (see src/lib/trader.ts). Token auth is enforced by the
// Python side; we just forward the request untouched.
for (const path of ["/status", "/stop", "/resume"]) {
  app.get(path, async (req, res) => {
    try {
      const qs = req.originalUrl.includes("?")
        ? req.originalUrl.slice(req.originalUrl.indexOf("?"))
        : "";
      const upstream = await fetch(
        `http://127.0.0.1:${KILL_SERVER_PORT}${path}${qs}`,
        { redirect: "manual" },
      );
      const location = upstream.headers.get("location");
      if (location) {
        res.redirect(upstream.status, location);
        return;
      }
      res
        .status(upstream.status)
        .type(upstream.headers.get("content-type") ?? "text/html")
        .send(await upstream.text());
    } catch {
      res
        .status(503)
        .type("text/html")
        .send(
          "<h1>Trading loop control panel unavailable</h1>" +
            "<p>The trading process may still be starting up. Refresh in a few seconds.</p>",
        );
    }
  });
}

export default app;
