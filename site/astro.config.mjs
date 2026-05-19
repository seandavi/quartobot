// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

// https://astro.build/config
export default defineConfig({
  site: "https://quartobot.github.io",
  base: "/quartobot",
  integrations: [
    starlight({
      title: "quartobot",
      description: "Citation resolution and manuscript-as-software CI for Quarto.",
      logo: { src: "./src/assets/logo.svg", replacesTitle: false },
      customCss: ["./src/styles/feature-bands.css"],
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/quartobot/quartobot",
        },
      ],
      editLink: {
        baseUrl: "https://github.com/quartobot/quartobot/edit/main/site/",
      },
      // Sidebar: Install is the first thing a new user needs, so it
      // sits at the top alongside Home. Everything below is grouped by
      // Diataxis quadrant — Tutorials (learning), How-to guides
      // (doing), Reference (information), Explanation (understanding).
      sidebar: [
        { label: "Home", link: "/" },
        { label: "Install", link: "/install/" },
        { label: "Coming from…", link: "/coming-from/" },
        {
          label: "Tutorials",
          items: [
            { label: "First manuscript (15 min)", link: "/first-manuscript/" },
            { label: "MCP + Claude Desktop", link: "/mcp-claude-desktop/" },
            { label: "Shell-tool agent", link: "/shell-tool-agent/" },
          ],
        },
        {
          label: "How-to guides",
          items: [
            { label: "Choose a path in", link: "/getting-started/" },
            { label: "Resolve a single citation", link: "/resolve-single-citation/" },
            { label: "Use a Quarto website", link: "/quarto-websites/" },
            { label: "Use a Quarto book", link: "/quarto-books/" },
            { label: "Use Jupyter notebooks", link: "/jupyter-notebooks/" },
            { label: "MCP server", link: "/mcp/" },
            { label: "Migrate from manubot", link: "/migrating-from-manubot/" },
            { label: "Validate a manuscript", link: "/validate-manuscript/" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "CLI", link: "/cli/" },
          ],
        },
        {
          label: "Explanation",
          items: [
            { label: "Design", link: "/design/" },
            { label: "Differences from manubot", link: "/differences-from-manubot/" },
          ],
        },
      ],
    }),
  ],
});
