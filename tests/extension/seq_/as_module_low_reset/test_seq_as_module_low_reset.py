from __future__ import absolute_import
from __future__ import print_function
import veriloggen
import seq_as_module_low_reset


expected_verilog = """
module test #
(
  parameter INTERVAL = 16
);

  reg CLK;
  reg nRST;
  wire [8-1:0] LED;

  blinkled
  #(
    .INTERVAL(INTERVAL)
  )
  uut
  (
    .CLK(CLK),
    .nRST(nRST),
    .LED(LED)
  );


  initial begin
    CLK = 0;
    forever begin
      #5 CLK = !CLK;
    end
  end


  initial begin
    nRST = 1;
    #100;
    nRST = 0;
    #100;
    nRST = 1;
    #1000;
    $finish;
  end


endmodule



module blinkled #
(
  parameter INTERVAL = 16
)
(
  input CLK,
  input nRST,
  output reg [8-1:0] LED
);

  reg [32-1:0] count;
  wire [32-1:0] _seq_count_0;

  always @(*) begin
    count = _seq_count_0;
  end

  wire [8-1:0] _seq_LED_1;

  always @(*) begin
    LED = _seq_LED_1;
  end

  localparam _seq_INTERVAL = INTERVAL;

  seq
  #(
    .INTERVAL(_seq_INTERVAL)
  )
  inst_seq
  (
    .CLK(CLK),
    .nRST(nRST),
    .i_LED(LED),
    .i_count(count),
    .count(_seq_count_0),
    .LED(_seq_LED_1)
  );


endmodule



module seq #
(
  parameter INTERVAL = 16
)
(
  input CLK,
  input nRST,
  input [8-1:0] i_LED,
  input [32-1:0] i_count,
  output reg [32-1:0] count,
  output reg [8-1:0] LED
);


  always @(posedge CLK or negedge nRST) begin
    if(~nRST) begin
      count <= 0;
      LED <= 0;
    end else begin
      $display("LED:%d count:%d", i_LED, i_count);
      if(i_count < INTERVAL - 1) begin
        count <= i_count + 1;
      end 
      if(i_count == INTERVAL - 1) begin
        count <= 0;
      end 
      if(i_count == INTERVAL - 1) begin
        LED <= i_LED + 1;
      end 
    end
  end


endmodule
"""

def test(monkeypatch):
    monkeypatch.setenv('RESET_ASYNC', 'Y')
    monkeypatch.setenv('RESET_ACTIVE_LOW', 'Y')
    veriloggen.reset()
    test_module = seq_as_module_low_reset.mkTest()
    code = test_module.to_verilog()

    from pyverilog.vparser.parser import VerilogParser
    from pyverilog.ast_code_generator.codegen import ASTCodeGenerator
    parser = VerilogParser()
    expected_ast = parser.parse(expected_verilog)
    codegen = ASTCodeGenerator()
    expected_code = codegen.visit(expected_ast)

    assert(expected_code == code)
