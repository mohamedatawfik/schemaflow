import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter as Router } from "react-router-dom";
//import { HashRouter as Router } from "react-router-dom";
import App from "./App";
import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider as MuiThemeProvider, createTheme } from "@mui/material/styles";
import { ThemeProvider as StylesThemeProvider } from "@mui/styles";

const rootElement = document.getElementById("root");
const root = createRoot(rootElement);
const theme = createTheme();

// strict mode is disabled so that findDOMNode warning is suppressed
root.render(
  <StylesThemeProvider theme={theme}>
    <MuiThemeProvider theme={theme}>
      <Router>
        <CssBaseline />
        <App />
      </Router>
    </MuiThemeProvider>
  </StylesThemeProvider>
);

//use this for strict mode, however it always throws the findDOMNode warning
/*root.render(
  <React.StrictMode>
    <Router>
      <CssBaseline />
      <App />
    </Router>
  </React.StrictMode>,
);
*/
