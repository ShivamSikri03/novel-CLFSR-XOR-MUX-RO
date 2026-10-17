module RO(
    input enable,
    (*DONT_TOUCH="TRUE"*) output wire RO1_out
);
`ifndef SYNTHESIS
    (*DONT_TOUCH="TRUE"*) wire w_nand,w1,w2,w3,w4, W1,W2,W3;
    integer d_nand = 1, d1 = 1, d2 = 1, d3 = 1, d4 = 1 , D1=1,D2=1,D3=1;
    always begin
        #7;
        d_nand = 1 + ({$urandom}%4);
        d1 = 1 + ({$urandom}%4);
        d2 = 1 + ({$urandom}%4);
        d3 = 1 + ({$urandom}%4);
        d4 = 1 + ({$urandom}%4);
        D1 = 1 + ({$urandom}%4);
    end
    assign #(d_nand) w_nand = ~(w4 & enable);
    assign #(d1) w1 = ~(w_nand);
    assign #(d2) w2 = ~(w1);
    assign #(d3) w3 = ~(w2);
    assign #(d4) w4 = ~(w3);
    assign #(D1) W1 = ~(w4);
    assign #(D2) W2 = ~(W1);
    assign #(D3) W3 = ~(W2);
    
    assign RO1_out = W3;

    initial begin
        force w_nand = 1'b0;
        #10;
        release w_nand;
    end
`else 
(*DONT_TOUCH="TRUE"*) wire w_nand,w1,w2,w3,w4, W1,W2,W3;
assign w_nand = ~(w4 & enable); 
assign w1 = ~(w_nand);
assign w2 = ~(w1);
assign w3 = ~(w2);
assign w4 = ~(w3);
assign W1 = ~(w4);
assign W2 = ~(W1);
assign W3 = ~(W2);
    
assign RO1_out = W3;
`endif 
endmodule
