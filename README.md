# Red Hill Contaminant Glossary

This website provides detail about contaminants that were detected across various monitoring efforts carried out in response to the Red Hill Water Crisis. Built with Next.js, React, and TypeScript.

_**Disclaimer**: This glossary is intended for general reference only. Information is compiled from publicly available regulatory databases, testing reports, and scientific literature. It does not constitute health, legal, or regulatory advice. Consult official sources and qualified professionals for guidance specific to your situation._

**Live:** https://examplesite.cloudflare.com  
**ArcGIS Hub:** [Embedded in hub page]

## Quick Start

### Local Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the app.

### Prerequisites
- Node.js 18+ (see `.nvmrc`)
- npm 11+

## Project Structure

```
src/
├── app/              # Next.js pages and layout
├── components/       # Reusable React components
└── lib/              # Utilities and types

public/               # Static assets
documentation/        # Project guides
pipeline/             # Data pipeline (R)
```

## Documentation

- **[ARCHITECTURE.md](./documentation/ARCHITECTURE.md)** — How the app works
- **[DEVELOPMENT.md](./documentation/DEVELOPMENT.md)** — Local setup guide
- **[DATA.md](./documentation/DATA.md)** — How to update contaminant data
- **[CONTRIBUTING.md](./documentation/CONTRIBUTING.md)** — Contributing guidelines
- **[DEPLOYMENT.md](./documentation/DEPLOYMENT.md)** — Deployment instructions

## Tech Stack

- **Frontend:** Next.js, React, TypeScript
- **Styling:** Tailwind CSS, shadcn/ui
- **Hosting:** Cloudflare Pages
- **Data Pipeline:** R → JSON
- **Code Quality:** ESLint, Prettier

## Key Features

- **Search & Filter:** Find contaminants by name, CASRN, aliases, or classification
- **Summary & Detailed Views:** Basic info for public, technical details for researchers
- **External Links:** Direct links to PubChem, Wikidata, regulatory databases
- **CSV Export:** Download filtered results
- **Responsive Design:** Works on desktop, tablet, and mobile
- **Accessible:** WCAG AA compliant

## Data Updates

Contaminant data is enriched via an R/Quarto pipeline and stored as JSON.

To update data:

```bash
cd pipeline/
quarto render process_data.qmd
cd ../
git add public/data.json
git commit -m "Update contaminants: [describe changes]"
git push
```

See [DATA.md](./documentation/DATA.md) for detailed instructions.

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and commit with conventional commits
3. Push and open a Pull Request
4. After review/approval, merge to `main`
5. Cloudflare auto-deploys

See [CONTRIBUTING.md](./documentation/CONTRIBUTING.md) for full guidelines.

## Deployment

The `main` branch is automatically deployed to Cloudflare Pages on every push.

Manual deployment:

```bash
npm run build
```

See [DEPLOYMENT.md](./documentation/DEPLOYMENT.md) for troubleshooting.

## Troubleshooting

**"Module not found"**
```bash
npm install
```

**"Port 3000 already in use"**
```bash
npm run dev -- -p 3001
```

**"TypeScript errors"**
```bash
npm run lint
```

See [CONTRIBUTING.md](./documentation/CONTRIBUTING.md#troubleshooting) for more.

## Support

For questions or issues:
- Check the [documentation](./documentation/)
- Review [existing issues](https://github.com/alemarieceria/red_hill_contaminant_glossary_app/issues)
- Open a [new issue](https://github.com/alemarieceria/red_hill_contaminant_glossary_app/issues/new)

## License

MIT License — see [LICENSE](./LICENSE) for details.

## Contributors

- **Eamonn Clarke, PhD** — Analytical Chemist, WRRC
- **Alemarie Ceria** — Developer, WRRC
- **Dilsiich Maui** — BSc Student Intern, TSPH

---

**Last updated:** July 2026  
**Maintained by:** Alemarie Ceria, WRRC