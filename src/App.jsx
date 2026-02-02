import React from "react";
import "./styles.css";
import { Route, Routes } from "react-router-dom";
import AdamantMain from "./pages/AdamantMain";
import { ToastContainer } from "react-toastify";

export default function App() {
  return (
    <>
      <div className="the_app">
        <Routes>
          <Route path="/" element={<AdamantMain />} />
          <Route path="/adamant" element={<AdamantMain />} />
        </Routes>
      </div>
      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        closeOnClick={true}
        pauseOnHover={true}
        draggable={false}
        progress={undefined} />
    </>
  );
};
