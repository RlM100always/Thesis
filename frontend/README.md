# B-SMART pharmacy-owner frontend

This React/Vite application is the interface for the B-SMART thesis prototype.
The revised initial domain is Bangladeshi retail pharmacies; generic retail
screens are the current foundation, while pharmacy batch/expiry and full
shop-constraint inputs are planned. See
[`../docs/PHARMACY_VERTICAL_SCOPE_AND_SUPERVISOR_GUIDELINE.md`](../docs/PHARMACY_VERTICAL_SCOPE_AND_SUPERVISOR_GUIDELINE.md)
before changing domain wording or recommendation flows.

## Development runtime

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.
