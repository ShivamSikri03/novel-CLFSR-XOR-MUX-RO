module RO_3(
    input enable,
    (*DONT_TOUCH="TRUE"*) output wire out
);
`ifndef SYNTHESIS
    (*DONT_TOUCH="TRUE"*) wire w1,w2,w_nand;
    integer d1 = 1, d2 = 1, d_nand = 1;
    
    always begin
        #4;
        d1 = 1 + ({$urandom} % 3);
        d2 = 1 + ({$urandom} % 3);
        d_nand = 1 + ({$urandom} % 3);
    end
    assign #(d1) w1 = ~(w_nand);
    assign #(d2) w2 = ~(w1);
    assign #(d_nand) w_nand = ~(w2 & enable);
    assign out = w_nand;

    initial begin
        force w_nand = 1'b0;
        #10; 
        release w_nand;
    end
`else 
(*DONT_TOUCH="TRUE"*) wire w1,w2,w_nand;
assign w1=~(w_nand);
assign w2=~w1;
assign w_nand = ~(w2 & enable);
assign  out=w_nand;
`endif 
endmodule
