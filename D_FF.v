module D_FF(
    input clk,
    input in,
    (*DONT_TOUCH="TRUE"*) output reg out
);
`ifndef SYNTHESIS
always @(posedge clk) begin
   #1 out <= in;
end
`else
always @(posedge clk) begin
   out <= in;
end
`endif
endmodule
