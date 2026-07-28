import express from "express";
import cookieParser from "cookie-parser";
import { resetDatabase } from "./db";
import { sessionAuth, csrfCheck } from "./auth";
import apiRouter from "./api";
import pingRouter from "./ping";
import frontRouter from "./front";

const app = express();
const port = process.env.PORT || 8000;

// Body & cookie parsing middlewares
app.use(cookieParser());
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// Session authentication and CSRF middlewares
app.use(sessionAuth);
app.use(csrfCheck);

// Reset endpoint
app.get("/__test/reset", (req, res) => {
  resetDatabase();
  res.setHeader("Content-Type", "text/plain");
  res.status(200).send("ok");
});

app.get("/__test/reset/", (req, res) => {
  resetDatabase();
  res.setHeader("Content-Type", "text/plain");
  res.status(200).send("ok");
});

// Mount routers
app.use(pingRouter);
app.use(apiRouter);
app.use(frontRouter);

// Fallback 404 handler
app.use((req, res) => {
  res.status(404).send("Not Found");
});

// Run server
app.listen(port, () => {
  console.log(`Healthchecks target server listening on port ${port}`);
});
