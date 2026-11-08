"""pdfgenerator — binario de render de PDF para Toscana Pastry.

Servicio HTTP independiente: recibe datos planos (JSON) y devuelve bytes de
PDF. Tres motores: PyMuPDF (reportes/export), ReportLab (presupuesto) y
WeasyPrint (lista de precios). core-api lo llama por HTTP.
"""

__version__ = "0.1.0"
