import React from 'react';
import './FlexiveisContent.css';

const FlexiveisContent = ({ selectedLine }) => {
  return (
    <div className="flexiveis-content">
      <h2>Flexíveis - {selectedLine}</h2>
      <p>Informações sobre produtos flexíveis para a linha {selectedLine}.</p>
    </div>
  );
};

export default FlexiveisContent;