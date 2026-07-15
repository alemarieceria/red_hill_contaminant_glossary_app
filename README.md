# Red Hill Contaminant Glossary

The Red Hill Contaminant Glossary is a public reference for searching and exploring information about contaminants identified through monitoring efforts related to the Red Hill water crisis.

_**Disclaimer**: This glossary is intended for general reference only. Information is compiled from publicly available regulatory databases, testing reports, and scientific literature. It does not constitute health, legal, or regulatory advice. Consult official sources and qualified professionals for guidance specific to your situation._

## Project Status

The glossary is under active development. The repository currently includes the application foundation, authoritative source workbooks, and the initial structure for a reproducible data pipeline.

## Application

The public site is a statically generated Next.js application deployed through Cloudflare Pages.

Current frontend technologies include:

- Next.js 16
- React 19
- TypeScript 5
- Tailwind CSS 4
- shadcn/ui and Base UI

## Local Development

Node.js 22.16.0 is specified in `.nvmrc`.

```bash
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Available checks:

```bash
npm run lint
npm run format:check
npm run build
```

The production build is exported to `out/` for static hosting.

## Repository Contents

```text
src/             Next.js application source
public/          Static assets and generated public data
data_pipeline/   Authoritative workbooks and Python pipeline source
```

The Python pipeline is still being implemented. Pipeline setup and release commands will be documented in `data_pipeline/README.md` when they are operational.

## Contributing and Corrections

Use a branch and pull request for repository changes. Keep scientific workbook updates separate from application or pipeline-code changes.

To report a possible data problem, request a feature, or ask a project question, open a [GitHub issue](https://github.com/alemarieceria/red_hill_contaminant_glossary_app/issues/new). Existing reports can be reviewed in the [issue tracker](https://github.com/alemarieceria/red_hill_contaminant_glossary_app/issues).

## License

This project is available under the [MIT License](./LICENSE).

## Project Team

- **Eamonn Clarke, PhD** — Analytical Chemist, WRRC
- **Alemarie Ceria** — Developer, WRRC
- **Dilsiich Maui** — BSc Student Intern, TSPH
